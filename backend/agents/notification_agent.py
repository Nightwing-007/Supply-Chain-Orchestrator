"""
Agent 6: Customer Notification Agent

Responsibilities:
  - Query notifications and orders tables for queued or pending customer communications
  - Retrieve customer contact info, order status, and operational context (e.g. weather delay, inventory backorder)
  - Invoke LLM (acting as an Empathetic Customer Success Representative) to draft tailored Email and SMS content
  - Dynamically adapt tone (apologetic for delays, reassuring for exceptions, enthusiastic for delivery)
  - Fall back to strict rule-based notification templates if the LLM is unavailable
  - Log execution audit to agent_task_log and update notifications status in database

Node interface (LangGraph-ready):
  Input:  dict  -- GlobalLogisticsState (or its notification sub-state)
  Output: dict  -- partial state update with { "notification": NotificationState }
"""

import json
import logging
import time
from datetime import datetime, timezone
from typing import Any

from db.connection import execute_query, execute_command
from services.llm_service import LLMService

logger = logging.getLogger(__name__)

# -- SQL Queries ----------------------------------------------

PENDING_NOTIFICATIONS_QUERY = """
    SELECT
        n.id              AS notification_id,
        n.order_id,
        n.channel,
        n.recipient,
        n.subject,
        n.body,
        n.status          AS notification_status,
        o.order_number,
        o.customer_name,
        o.customer_email,
        o.customer_phone,
        o.delivery_address,
        o.status          AS order_status,
        o.promised_at,
        o.total_amount
    FROM notifications n
    JOIN orders o ON o.id = n.order_id
    WHERE n.status = 'queued'
    ORDER BY n.created_at ASC
"""

RECENT_ORDERS_QUERY = """
    SELECT
        o.id              AS order_id,
        o.order_number,
        o.customer_name,
        o.customer_email,
        o.customer_phone,
        o.delivery_address,
        o.status          AS order_status,
        o.promised_at,
        o.total_amount
    FROM orders o
    ORDER BY o.updated_at DESC, o.id DESC
    LIMIT 5
"""

UPDATE_NOTIFICATION_STATUS = """
    UPDATE notifications
    SET status = 'sent'::notification_status,
        sent_at = NOW()
    WHERE id = $1
"""

LOG_AGENT_TASK = """
    INSERT INTO agent_task_log (agent, task_type, input_payload, output_payload, status, duration_ms, completed_at)
    VALUES ($1, $2, $3::jsonb, $4::jsonb, $5, $6, NOW())
"""


# =============================================================
#  Template Generator (Fallback)
# =============================================================

def build_templated_notification(
    order_number: str,
    customer_name: str,
    order_status: str,
    event_type: str = "status_update",
    reason: str = "",
) -> dict[str, Any]:
    """
    Generate deterministic rule-based email and SMS templates.
    Used when the LLM is unavailable.

    Returns:
        Dict containing email_subject, email_body, sms_body, tone.
    """
    clean_name = customer_name if customer_name else "Valued Customer"

    if "delay" in event_type.lower() or "delay" in reason.lower() or order_status == "exception":
        tone = "apologetic"
        subject = f"Important Update Regarding Order #{order_number}"
        email_body = (
            f"Dear {clean_name},\n\n"
            f"We are writing to inform you that your order #{order_number} is experiencing a brief delay. "
            f"{reason if reason else 'Our team is working diligently to minimize impact.'}\n\n"
            f"Current Order Status: {order_status.upper()}.\n"
            f"We apologize for any inconvenience caused and will update you as soon as your shipment is en route.\n\n"
            f"Best regards,\nCustomer Success Team"
        )
        sms_body = f"Order #{order_number} Update: Your delivery is delayed. Status: {order_status}. We apologize for the inconvenience."

    elif order_status in ("delivered", "shipped", "out_for_delivery"):
        tone = "enthusiastic"
        subject = f"Great news! Order #{order_number} is {order_status.replace('_', ' ')}"
        email_body = (
            f"Hi {clean_name},\n\n"
            f"Good news! Your order #{order_number} status is now: {order_status.replace('_', ' ').upper()}.\n\n"
            f"Thank you for shopping with us!\n\n"
            f"Warm regards,\nCustomer Success Team"
        )
        sms_body = f"Great news! Order #{order_number} status is now {order_status.replace('_', ' ')}. Thank you for choosing us!"

    else:
        tone = "informative"
        subject = f"Update regarding your order #{order_number}"
        email_body = (
            f"Hello {clean_name},\n\n"
            f"Your order #{order_number} status has been updated to: {order_status.upper()}.\n"
            f"Thank you for your patience.\n\n"
            f"Best regards,\nCustomer Success Team"
        )
        sms_body = f"Order #{order_number} update: Status is {order_status}. Thank you for your order."

    return {
        "email_subject": subject,
        "email_body": email_body,
        "sms_body": sms_body[:160],  # Ensure SMS length cap
        "tone": tone,
    }


# =============================================================
#  LLM Integration
# =============================================================

SYSTEM_INSTRUCTION = """You are an Empathetic Customer Success Representative and Communications Manager.
Draft tailored, professional Email and SMS messages for logistics customer notifications.
Dynamically adjust your tone based on operational news:
- Apologetic and reassuring for delays, backorders, or disruptions
- Enthusiastic and warm for successful deliveries or dispatches
- Clear and professional for status updates
Always respond with valid JSON matching the exact schema provided."""

NOTIFICATION_PROMPT_TEMPLATE = """Draft a Communication Draft Plan for the following order notification context.

## Order Information
- Order Number: {order_number}
- Customer Name: {customer_name}
- Customer Email: {customer_email}
- Customer Phone: {customer_phone}
- Order Status: {order_status}
- Promised Delivery SLA: {promised_at}
- Event / Reason: {event_reason}

## Operational Context / Agent Insights
{context_notes}

## Current Date
{current_date}

## Required Output Schema
Return a JSON object with this exact structure:
{{
  "communication_plan": {{
    "email": {{
      "subject": "<compelling, context-appropriate subject line>",
      "body": "<professional, well-structured email body with greeting and sign-off>"
    }},
    "sms": {{
      "body": "<concise SMS message under 160 characters>"
    }},
    "tone": "<apologetic|enthusiastic|informative|reassuring>",
    "action_taken": "<description of dispatch communication strategy>"
  }},
  "summary": "<one-sentence summary of the customer notification draft>"
}}

Rules:
- Keep the SMS body strictly under 160 characters.
- Ensure the customer's name and order number are included in both Email and SMS.
- If there is a delay or exception, acknowledge the issue directly and express genuine empathy.
"""


# =============================================================
#  Core Agent Function
# =============================================================

async def customer_notification_agent(
    state: dict[str, Any],
    *,
    llm_service: LLMService | None = None,
) -> dict[str, Any]:
    """
    Customer Notification Agent -- LangGraph node function.

    Pipeline:
      1. Query queued notifications or active order status from database via asyncpg.
      2. Extract event reasons (e.g. weather delay from Agent 4, backorder from Agent 1).
      3. Call LLM (Customer Success Rep) for personalized Email and SMS drafting.
      4. Fall back to deterministic templates if the LLM is unavailable.
      5. Mark queued notifications as 'sent' in database.
      6. Log task execution to agent_task_log.
      7. Return partial state update for GlobalLogisticsState.

    Args:
        state: Current GlobalLogisticsState dict.
        llm_service: Optional injected LLMService (for testability).

    Returns:
        dict with updated ``notification`` sub-state.
    """
    t0 = time.perf_counter()
    task_status = "completed"
    error_msg = None
    notif_id = 0

    try:
        # -- Step 1: Fetch pending queued notifications -------
        queued_rows = await execute_query(PENDING_NOTIFICATIONS_QUERY)
        queued_notifs = _serialise_rows(queued_rows)

        order_data: dict[str, Any]
        event_reason = state.get("event_type") or state.get("reason") or ""
        context_notes = state.get("error") or state.get("query") or "Standard operational status check."

        if queued_notifs:
            target_item = queued_notifs[0]
            notif_id = target_item["notification_id"]
            order_data = target_item
            event_reason = event_reason or f"Queued notification for status {target_item['order_status']}"
        else:
            # Fallback to recent order if no queued notification exists
            recent_orders = await execute_query(RECENT_ORDERS_QUERY)
            orders_serialised = _serialise_rows(recent_orders)
            if orders_serialised:
                order_data = orders_serialised[0]
                event_reason = event_reason or f"Order status update to {order_data['order_status']}"
            else:
                # Empty DB fallback
                order_data = {
                    "order_id": 1,
                    "order_number": "ORD-2026-00001",
                    "customer_name": "Valued Customer",
                    "customer_email": "customer@example.com",
                    "customer_phone": "+91-98765-43210",
                    "order_status": "confirmed",
                    "promised_at": "2026-07-30T12:00:00",
                }
                event_reason = event_reason or "Order confirmation update"

        logger.info("Drafting notification for Order #%s (Status: %s)",
                    order_data["order_number"], order_data["order_status"])

        # -- Step 2: Call LLM for Communication Plan ----------
        comm_result: dict[str, Any]

        if llm_service is None:
            llm_service = LLMService()

        try:
            prompt = NOTIFICATION_PROMPT_TEMPLATE.format(
                order_number=order_data["order_number"],
                customer_name=order_data["customer_name"],
                customer_email=order_data.get("customer_email", "customer@example.com"),
                customer_phone=order_data.get("customer_phone", "N/A"),
                order_status=order_data["order_status"],
                promised_at=order_data.get("promised_at", "N/A"),
                event_reason=event_reason,
                context_notes=context_notes,
                current_date=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            )
            comm_result = await llm_service.generate(
                prompt,
                system_instruction=SYSTEM_INSTRUCTION,
                temperature=0.3,
                max_output_tokens=4096,
            )
            logger.info("LLM notification draft generated successfully")
        except Exception as exc:
            logger.error("LLM notification call failed, using deterministic template: %s", exc)
            tmpl = build_templated_notification(
                order_number=order_data["order_number"],
                customer_name=order_data["customer_name"],
                order_status=order_data["order_status"],
                event_type=event_reason,
                reason=context_notes,
            )
            comm_result = {
                "communication_plan": {
                    "email": {
                        "subject": tmpl["email_subject"],
                        "body": tmpl["email_body"],
                    },
                    "sms": {
                        "body": tmpl["sms_body"],
                    },
                    "tone": tmpl["tone"],
                    "action_taken": "Deterministic fallback notification template generated.",
                },
                "summary": f"Fallback notification template generated for Order #{order_data['order_number']}.",
            }

        # -- Step 3: Update DB notification status if queued ---
        if notif_id > 0:
            try:
                await execute_command(UPDATE_NOTIFICATION_STATUS, notif_id)
                logger.info("Marked notification #%d as sent", notif_id)
            except Exception as db_exc:
                logger.warning("Failed to update notification status in DB: %s", db_exc)

        # -- Step 4: Assemble state update --------------------
        comm_plan = comm_result.get("communication_plan", {})
        email_data = comm_plan.get("email", {})
        sms_data = comm_plan.get("sms", {})

        result: dict[str, Any] = {
            "notification": {
                "order_id": order_data.get("order_id", 1),
                "customer_name": order_data["customer_name"],
                "customer_email": order_data.get("customer_email", ""),
                "customer_phone": order_data.get("customer_phone", ""),
                "channel": order_data.get("channel", "email"),
                "event_type": event_reason if event_reason else "order_update",
                "message_body": email_data.get("body", ""),
                "notification_id": notif_id,
                # Extended metadata
                "_email_subject": email_data.get("subject", ""),
                "_sms_body": sms_data.get("body", ""),
                "_tone": comm_plan.get("tone", "informative"),
                "_draft_plan": comm_result,
            },
        }
        return result

    except Exception as exc:
        task_status = "failed"
        error_msg = str(exc)
        logger.exception("Customer Notification Agent failed: %s", exc)
        return {
            "notification": {
                "order_id": 0,
                "customer_name": "UNKNOWN",
                "customer_email": "",
                "customer_phone": "",
                "channel": "email",
                "event_type": "error",
                "message_body": "",
                "notification_id": 0,
            },
            "error": f"Customer Notification Agent error: {error_msg}",
        }

    finally:
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        try:
            input_payload = json.dumps({
                "query": state.get("query", ""),
                "intent": state.get("intent", ""),
            })
            output_summary = json.dumps({
                "notification_id": notif_id,
                "status": task_status,
            })
            await execute_command(
                LOG_AGENT_TASK,
                "customer_notification",
                "notification_draft",
                input_payload,
                output_summary,
                task_status,
                elapsed_ms,
            )
        except Exception as log_exc:
            logger.warning("Failed to log agent task: %s", log_exc)


# =============================================================
#  Helpers
# =============================================================

def _serialise_rows(rows: list[dict]) -> list[dict]:
    """
    Convert asyncpg Row dicts to JSON-safe dicts.
    Handles Decimal -> float, date/datetime -> ISO string.
    """
    import decimal
    from datetime import date as date_type

    clean = []
    for row in rows:
        cleaned_row = {}
        for key, value in row.items():
            if isinstance(value, decimal.Decimal):
                cleaned_row[key] = float(value)
            elif isinstance(value, datetime):
                cleaned_row[key] = value.isoformat()
            elif isinstance(value, date_type):
                cleaned_row[key] = value.isoformat()
            else:
                cleaned_row[key] = value
        clean.append(cleaned_row)
    return clean
