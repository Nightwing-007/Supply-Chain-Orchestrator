import { useState, useEffect, useMemo } from "react";
import { 
  Plus, Edit, Trash2, RefreshCw, Search, Package, AlertTriangle, 
  CheckCircle2, DollarSign, Layers, X, ChevronLeft, ChevronRight,
  TrendingUp, ShoppingBag, Eye, Calendar, User, MapPin, CreditCard, Filter, Clock, ShoppingCart
} from "lucide-react";
import { motion } from "framer-motion";
import { toast } from "react-hot-toast";
import { fetchProducts, createProduct, updateProduct, deleteProduct, fetchSalesHistory, createSaleTransaction } from "../api";

export default function ShopManagement({ onTriggerRestock }) {
  // Sub-Tab Switcher State ('catalog' | 'sales')
  const [activeSubTab, setActiveSubTab] = useState("catalog");

  // Product Catalog State
  const [products, setProducts] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [editingProduct, setEditingProduct] = useState(null);

  // Sales History State
  const [salesData, setSalesData] = useState({ summary: {}, orders: [] });
  const [isLoadingSales, setIsLoadingSales] = useState(false);
  const [salesSearchQuery, setSalesSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [selectedOrder, setSelectedOrder] = useState(null);

  // New Sale Checkout Modal State
  const [isSaleModalOpen, setIsSaleModalOpen] = useState(false);
  const [saleForm, setSaleForm] = useState({
    product_id: "",
    quantity: 1,
    customer_name: "",
    customer_email: "",
    customer_phone: "",
    delivery_city: "Mumbai",
    delivery_address: "Marine Drive Hub",
  });
  const [isSubmittingSale, setIsSubmittingSale] = useState(false);

  // Catalog Pagination State
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 10;

  // Sales Pagination State
  const [salesCurrentPage, setSalesCurrentPage] = useState(1);
  const salesItemsPerPage = 10;

  // New Product Form State
  const [newProduct, setNewProduct] = useState({
    sku: "",
    name: "",
    category: "Electronics",
    unit_price: 49.99,
    quantity_on_hand: 50,
    reorder_point: 20,
  });

  // Edit Product Form State
  const [editForm, setEditForm] = useState({
    id: null,
    sku: "",
    name: "",
    category: "",
    unit_price: 0,
    quantity_on_hand: 0,
    reorder_point: 10,
  });

  const [formError, setFormError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const loadProducts = async () => {
    setIsLoading(true);
    try {
      const data = await fetchProducts();
      setProducts(data);
    } catch (err) {
      console.error("Failed to load products", err);
      toast.error("Failed to load products from database.");
    } finally {
      setIsLoading(false);
    }
  };

  const loadSales = async () => {
    setIsLoadingSales(true);
    try {
      const data = await fetchSalesHistory();
      setSalesData(data);
    } catch (err) {
      console.error("Failed to load sales history", err);
      toast.error("Failed to load sales history from database.");
    } finally {
      setIsLoadingSales(false);
    }
  };

  useEffect(() => {
    loadProducts();
  }, []);

  useEffect(() => {
    if (activeSubTab === "sales") {
      loadSales();
    }
  }, [activeSubTab]);

  const handleCreateProduct = async (e) => {
    e.preventDefault();
    setFormError("");
    setIsSubmitting(true);

    try {
      await createProduct(newProduct);
      setIsAddModalOpen(false);
      setNewProduct({
        sku: "",
        name: "",
        category: "Electronics",
        unit_price: 49.99,
        quantity_on_hand: 50,
        reorder_point: 20,
      });
      toast.success(`Product "${newProduct.name}" created successfully!`);
      await loadProducts();
    } catch (err) {
      const msg = err.response?.data?.detail || "Failed to create product";
      setFormError(msg);
      toast.error(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleUpdateProduct = async (e) => {
    e.preventDefault();
    setFormError("");
    setIsSubmitting(true);

    try {
      await updateProduct(editForm.id, {
        name: editForm.name,
        category: editForm.category,
        unit_price: editForm.unit_price,
        quantity_on_hand: editForm.quantity_on_hand,
        reorder_point: editForm.reorder_point,
      });
      setEditingProduct(null);
      toast.success(`Product updated successfully!`);
      await loadProducts();
    } catch (err) {
      const msg = err.response?.data?.detail || "Failed to update product";
      setFormError(msg);
      toast.error(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDeleteProduct = async (p) => {
    if (window.confirm(`Are you sure you want to remove "${p.name}" (${p.sku}) from the catalog?`)) {
      try {
        await deleteProduct(p.id);
        toast.success(`Product "${p.name}" removed successfully!`);
        await loadProducts();
      } catch (err) {
        toast.error(err.response?.data?.detail || "Failed to delete product");
      }
    }
  };

  const openEditModal = (p) => {
    setEditForm({
      id: p.id,
      sku: p.sku,
      name: p.name,
      category: p.category || "General",
      unit_price: p.unit_price || 0,
      quantity_on_hand: p.quantity_on_hand || 0,
      reorder_point: p.reorder_point || 10,
    });
    setEditingProduct(p);
  };

  const openSaleModal = (p = null) => {
    setSaleForm({
      product_id: p ? p.id : (products[0]?.id || ""),
      quantity: 1,
      customer_name: "Rahul Mehta",
      customer_email: "rahul@example.com",
      customer_phone: "+91-98765-43210",
      delivery_city: "Mumbai",
      delivery_address: "Bandla West, Mumbai",
    });
    setIsSaleModalOpen(true);
  };

  const handleProcessSale = async (e) => {
    e.preventDefault();
    setIsSubmittingSale(true);
    try {
      const payload = {
        customer_name: saleForm.customer_name,
        customer_email: saleForm.customer_email,
        customer_phone: saleForm.customer_phone,
        delivery_city: saleForm.delivery_city,
        delivery_address: saleForm.delivery_address,
        items: [
          {
            product_id: Number(saleForm.product_id),
            quantity: Number(saleForm.quantity),
          }
        ]
      };
      const res = await createSaleTransaction(payload);
      toast.success(res.message || "Sale completed successfully!");
      setIsSaleModalOpen(false);

      // Refresh catalog stock and sales history
      await loadProducts();
      if (activeSubTab === "sales") {
        await loadSales();
      }
    } catch (err) {
      const msg = err.response?.data?.detail || "Failed to process sale transaction";
      toast.error(msg);
    } finally {
      setIsSubmittingSale(false);
    }
  };

  // Instant real-time filter calculation for Catalog
  const filteredProducts = useMemo(() => {
    const q = searchQuery.toLowerCase().trim();
    if (!q) return products;
    return products.filter((p) => {
      const nameMatch = p.name ? p.name.toLowerCase().includes(q) : false;
      const skuMatch = p.sku ? p.sku.toLowerCase().includes(q) : false;
      const catMatch = p.category ? p.category.toLowerCase().includes(q) : false;
      const whMatch = p.warehouse_code ? p.warehouse_code.toLowerCase().includes(q) : false;
      return nameMatch || skuMatch || catMatch || whMatch;
    });
  }, [products, searchQuery]);

  useEffect(() => {
    setCurrentPage(1);
  }, [searchQuery]);

  const totalPages = Math.max(1, Math.ceil(filteredProducts.length / itemsPerPage));
  const paginatedProducts = useMemo(() => {
    const start = (currentPage - 1) * itemsPerPage;
    return filteredProducts.slice(start, start + itemsPerPage);
  }, [filteredProducts, currentPage, itemsPerPage]);

  // Real-time filtering for Sales History
  const filteredOrders = useMemo(() => {
    let list = salesData.orders || [];
    if (statusFilter !== "all") {
      list = list.filter((o) => o.status === statusFilter);
    }
    const q = salesSearchQuery.toLowerCase().trim();
    if (!q) return list;
    return list.filter((o) => {
      const numMatch = o.order_number ? o.order_number.toLowerCase().includes(q) : false;
      const custMatch = o.customer_name ? o.customer_name.toLowerCase().includes(q) : false;
      const emailMatch = o.customer_email ? o.customer_email.toLowerCase().includes(q) : false;
      const cityMatch = o.delivery_city ? o.delivery_city.toLowerCase().includes(q) : false;
      const itemMatch = o.items ? o.items.some((i) => 
        (i.product_name && i.product_name.toLowerCase().includes(q)) || 
        (i.product_sku && i.product_sku.toLowerCase().includes(q))
      ) : false;
      return numMatch || custMatch || emailMatch || cityMatch || itemMatch;
    });
  }, [salesData.orders, statusFilter, salesSearchQuery]);

  useEffect(() => {
    setSalesCurrentPage(1);
  }, [salesSearchQuery, statusFilter]);

  const salesTotalPages = Math.max(1, Math.ceil(filteredOrders.length / salesItemsPerPage));
  const paginatedOrders = useMemo(() => {
    const start = (salesCurrentPage - 1) * salesItemsPerPage;
    return filteredOrders.slice(start, start + salesItemsPerPage);
  }, [filteredOrders, salesCurrentPage, salesItemsPerPage]);

  const getStatusBadge = (status) => {
    switch (status) {
      case "delivered":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <CheckCircle2 size={12} /> Delivered
          </span>
        );
      case "confirmed":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <CheckCircle2 size={12} /> Confirmed
          </span>
        );
      case "out_for_delivery":
      case "shipped":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-sky-500/10 text-sky-400 border border-sky-500/20">
            <Package size={12} /> Out for Delivery
          </span>
        );
      case "processing":
      case "picking":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20">
            <RefreshCw size={12} className="animate-spin" /> Processing
          </span>
        );
      case "cancelled":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-red-500/10 text-red-400 border border-red-500/20">
            <AlertTriangle size={12} /> Cancelled
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-slate-500/10 text-slate-400 border border-slate-500/20 capitalize">
            <Clock size={12} /> {status || 'Pending'}
          </span>
        );
    }
  };

  const selectedProductObj = products.find(p => p.id === Number(saleForm.product_id));

  return (
    <div className="space-y-8">
      {/* Header & Sub-Tab Navigation */}
      <header className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-subtle pb-6">
        <div>
          <h1 className="text-4xl font-light tracking-tight mb-1">Shop Management Portal</h1>
          <p className="text-text-secondary text-sm">Direct owner control portal for live product catalog, CRUD operations, and sales history.</p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {/* Sub-Tab Selector */}
          <div className="flex items-center bg-bg-panel/70 p-1 rounded-xl border border-border-panel">
            <button
              onClick={() => setActiveSubTab("catalog")}
              className={`px-4 py-2 rounded-lg text-xs font-medium transition-all cursor-pointer flex items-center gap-2 ${
                activeSubTab === "catalog"
                  ? "bg-accent-primary text-bg-base shadow"
                  : "text-text-secondary hover:text-text-primary"
              }`}
            >
              <Package size={14} />
              <span>Product Catalog</span>
            </button>
            <button
              onClick={() => setActiveSubTab("sales")}
              className={`px-4 py-2 rounded-lg text-xs font-medium transition-all cursor-pointer flex items-center gap-2 ${
                activeSubTab === "sales"
                  ? "bg-accent-primary text-bg-base shadow"
                  : "text-text-secondary hover:text-text-primary"
              }`}
            >
              <TrendingUp size={14} />
              <span>Sales History</span>
              {salesData.summary?.total_orders ? (
                <span className="ml-1 px-1.5 py-0.5 rounded-full text-[10px] bg-bg-base/30 font-mono">
                  {salesData.summary.total_orders}
                </span>
              ) : null}
            </button>
          </div>

          <button
            onClick={activeSubTab === "catalog" ? loadProducts : loadSales}
            className="p-2.5 bg-border-panel/20 text-text-secondary hover:text-text-primary rounded-xl border border-border-panel transition-colors cursor-pointer"
            title="Refresh Data"
          >
            <RefreshCw size={16} className={isLoading || isLoadingSales ? "animate-spin" : ""} />
          </button>
          
          <button
            onClick={() => openSaleModal()}
            className="px-4 py-2.5 bg-emerald-600 text-white font-medium rounded-xl text-sm hover:bg-emerald-500 transition-colors flex items-center gap-2 cursor-pointer shadow-lg"
          >
            <ShoppingCart size={16} />
            <span>Record New Sale</span>
          </button>

          {activeSubTab === "catalog" && (
            <button
              onClick={() => setIsAddModalOpen(true)}
              className="px-4 py-2.5 bg-accent-primary text-bg-base font-medium rounded-xl text-sm hover:opacity-90 transition-opacity flex items-center gap-2 cursor-pointer shadow-lg"
            >
              <Plus size={16} />
              <span>Add Product</span>
            </button>
          )}
        </div>
      </header>

      {/* ────────────────── SUB-TAB 1: PRODUCT CATALOG ────────────────── */}
      {activeSubTab === "catalog" && (
        <>
          {/* Search & Filter Bar */}
          <div className="flex items-center justify-between gap-4">
            <div className="relative flex-1 max-w-md">
              <Search size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-text-secondary" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search by SKU, Product Name, or Category..."
                className="w-full bg-bg-panel/50 border border-border-panel rounded-xl pl-10 pr-10 py-2.5 text-sm text-text-primary placeholder:text-text-placeholder focus:outline-none focus:border-accent-primary transition-colors"
              />
              {searchQuery && (
                <button
                  onClick={() => setSearchQuery("")}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-text-secondary hover:text-text-primary transition-colors cursor-pointer"
                  title="Clear search"
                >
                  <X size={14} />
                </button>
              )}
            </div>
            <div className="text-xs font-mono text-text-secondary">
              Showing <span className="text-text-primary font-medium">{filteredProducts.length}</span> of {products.length} Products
            </div>
          </div>

          {/* Products Table */}
          {isLoading ? (
            <div className="text-text-secondary text-sm py-12 text-center">Loading product catalog...</div>
          ) : (
            <div className="space-y-4">
              <div className="glass-card rounded-2xl overflow-hidden">
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm border-collapse">
                    <thead>
                      <tr className="border-b border-subtle surface-tint text-xs font-medium text-text-secondary uppercase tracking-wider">
                        <th className="py-4 px-6">SKU</th>
                        <th className="py-4 px-6">Product Details</th>
                        <th className="py-4 px-6">Unit Price</th>
                        <th className="py-4 px-6">Stock Level</th>
                        <th className="py-4 px-6">Reorder Threshold</th>
                        <th className="py-4 px-6">Health Status</th>
                        <th className="py-4 px-6 text-right">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border-panel">
                      {paginatedProducts.map((p) => {
                        const isLow = p.quantity_on_hand <= p.reorder_point;
                        const isCritical = p.quantity_on_hand === 0;

                        return (
                          <tr key={p.id} className="surface-tint-hover transition-colors">
                            <td className="py-4 px-6 font-mono text-xs text-accent-primary font-medium">{p.sku}</td>
                            <td className="py-4 px-6">
                              <div className="font-medium text-text-primary">{p.name}</div>
                              <div className="text-xs text-text-secondary">{p.category || 'General'}</div>
                            </td>
                            <td className="py-4 px-6 font-mono text-text-primary">${Number(p.unit_price || 0).toFixed(2)}</td>
                            <td className="py-4 px-6 font-mono font-medium">{p.quantity_on_hand} units</td>
                            <td className="py-4 px-6 font-mono text-text-secondary">{p.reorder_point} units</td>
                            <td className="py-4 px-6">
                              {isCritical ? (
                                <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-red-500/10 text-red-400 border border-red-500/20">
                                  <AlertTriangle size={12} /> Out of Stock
                                </span>
                              ) : isLow ? (
                                <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20">
                                  <AlertTriangle size={12} /> Low Stock
                                </span>
                              ) : (
                                <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                                  <CheckCircle2 size={12} /> Healthy
                                </span>
                              )}
                            </td>
                            <td className="py-4 px-6 text-right">
                              <div className="flex items-center justify-end gap-2">
                                <button
                                  onClick={() => openSaleModal(p)}
                                  disabled={p.quantity_on_hand === 0}
                                  className="px-2.5 py-1 bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 hover:bg-emerald-500/20 rounded-lg text-xs font-medium transition-colors cursor-pointer flex items-center gap-1 disabled:opacity-30 disabled:cursor-not-allowed"
                                  title="Sell Item"
                                >
                                  <ShoppingCart size={13} /> Sell
                                </button>
                                <button
                                  onClick={() => openEditModal(p)}
                                  className="p-1.5 bg-border-panel/30 text-text-secondary hover:text-text-primary rounded-lg transition-colors cursor-pointer"
                                  title="Edit Product"
                                >
                                  <Edit size={15} />
                                </button>
                                <button
                                  onClick={() => handleDeleteProduct(p)}
                                  className="p-1.5 bg-red-500/10 text-red-400 hover:bg-red-500/20 hover:text-red-300 rounded-lg transition-colors cursor-pointer border border-red-500/20"
                                  title="Delete Product"
                                >
                                  <Trash2 size={15} />
                                </button>
                                {isLow && onTriggerRestock && (
                                  <button
                                    onClick={() => onTriggerRestock(p)}
                                    className="px-2.5 py-1 bg-accent-primary/20 text-accent-primary border border-accent-primary/30 rounded-lg text-xs font-medium hover:bg-accent-primary hover:text-bg-base transition-colors cursor-pointer flex items-center gap-1"
                                  >
                                    <RefreshCw size={12} /> Restock
                                  </button>
                                )}
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                      {filteredProducts.length === 0 && (
                        <tr>
                          <td colSpan={7} className="py-8 text-center text-text-secondary text-sm">
                            No products match your search query "{searchQuery}".
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Pagination Controls */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pt-2 px-2">
                <div className="text-xs text-text-secondary">
                  Showing <span className="font-medium text-text-primary">{filteredProducts.length > 0 ? (currentPage - 1) * itemsPerPage + 1 : 0}</span> to <span className="font-medium text-text-primary">{Math.min(currentPage * itemsPerPage, filteredProducts.length)}</span> of <span className="font-medium text-text-primary">{filteredProducts.length}</span> products
                </div>
                <div className="flex items-center gap-2">
                  <button
                    disabled={currentPage === 1}
                    onClick={() => setCurrentPage((prev) => Math.max(1, prev - 1))}
                    className="p-2 bg-border-panel/20 text-text-secondary hover:text-text-primary border border-border-panel rounded-xl disabled:opacity-30 disabled:cursor-not-allowed transition-colors cursor-pointer flex items-center gap-1 text-xs"
                  >
                    <ChevronLeft size={14} /> Previous
                  </button>
                  <span className="px-3 py-1 text-xs font-mono text-text-secondary bg-border-panel/20 rounded-xl border border-border-panel">
                    Page <strong className="text-text-primary">{currentPage}</strong> of {totalPages}
                  </span>
                  <button
                    disabled={currentPage >= totalPages}
                    onClick={() => setCurrentPage((prev) => Math.min(totalPages, prev + 1))}
                    className="p-2 bg-border-panel/20 text-text-secondary hover:text-text-primary border border-border-panel rounded-xl disabled:opacity-30 disabled:cursor-not-allowed transition-colors cursor-pointer flex items-center gap-1 text-xs"
                  >
                    Next <ChevronRight size={14} />
                  </button>
                </div>
              </div>
            </div>
          )}
        </>
      )}

      {/* ────────────────── SUB-TAB 2: SALES HISTORY & ANALYTICS ────────────────── */}
      {activeSubTab === "sales" && (
        <div className="space-y-6">
          {/* Revenue & Sales Summary KPI Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="glass-card p-5 rounded-2xl flex items-center justify-between">
              <div>
                <span className="text-xs uppercase tracking-wider text-text-secondary font-medium">Total Revenue</span>
                <div className="text-2xl font-light font-mono text-emerald-400 mt-1">
                  ${salesData.summary?.total_revenue ? Number(salesData.summary.total_revenue).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : "0.00"}
                </div>
              </div>
              <div className="p-3 bg-emerald-500/10 text-emerald-400 rounded-xl border border-emerald-500/20">
                <DollarSign size={20} />
              </div>
            </div>

            <div className="glass-card p-5 rounded-2xl flex items-center justify-between">
              <div>
                <span className="text-xs uppercase tracking-wider text-text-secondary font-medium">Total Orders</span>
                <div className="text-2xl font-light text-text-primary mt-1 font-mono">
                  {salesData.summary?.total_orders || 0}
                </div>
              </div>
              <div className="p-3 bg-sky-500/10 text-sky-400 rounded-xl border border-sky-500/20">
                <ShoppingBag size={20} />
              </div>
            </div>

            <div className="glass-card p-5 rounded-2xl flex items-center justify-between">
              <div>
                <span className="text-xs uppercase tracking-wider text-text-secondary font-medium">Avg Order Value</span>
                <div className="text-2xl font-light font-mono text-text-primary mt-1">
                  ${salesData.summary?.avg_order_value ? Number(salesData.summary.avg_order_value).toFixed(2) : "0.00"}
                </div>
              </div>
              <div className="p-3 bg-amber-500/10 text-amber-400 rounded-xl border border-amber-500/20">
                <TrendingUp size={20} />
              </div>
            </div>

            <div className="glass-card p-5 rounded-2xl flex items-center justify-between">
              <div>
                <span className="text-xs uppercase tracking-wider text-text-secondary font-medium">Delivered Orders</span>
                <div className="text-2xl font-light text-accent-primary mt-1 font-mono">
                  {salesData.summary?.delivered_orders || 0}
                  <span className="text-xs text-text-secondary ml-1 font-mono">
                    ({salesData.summary?.total_orders ? Math.round((salesData.summary.delivered_orders / salesData.summary.total_orders) * 100) : 0}%)
                  </span>
                </div>
              </div>
              <div className="p-3 bg-accent-primary/10 text-accent-primary rounded-xl border border-accent-primary/20">
                <CheckCircle2 size={20} />
              </div>
            </div>
          </div>

          {/* Search & Filter Toolbar */}
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-4">
            <div className="relative flex-1 max-w-md">
              <Search size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-text-secondary" />
              <input
                type="text"
                value={salesSearchQuery}
                onChange={(e) => setSalesSearchQuery(e.target.value)}
                placeholder="Search by Order #, Customer Name, City, or Product..."
                className="w-full bg-bg-panel/50 border border-border-panel rounded-xl pl-10 pr-10 py-2.5 text-sm text-text-primary placeholder:text-text-placeholder focus:outline-none focus:border-accent-primary transition-colors"
              />
              {salesSearchQuery && (
                <button
                  onClick={() => setSalesSearchQuery("")}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-text-secondary hover:text-text-primary cursor-pointer"
                  title="Clear search"
                >
                  <X size={14} />
                </button>
              )}
            </div>

            {/* Status Filter */}
            <div className="flex items-center gap-2">
              <Filter size={14} className="text-text-secondary" />
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="bg-bg-panel/50 border border-border-panel rounded-xl px-3 py-2 text-xs text-text-primary focus:outline-none focus:border-accent-primary cursor-pointer"
              >
                <option value="all">All Order Statuses</option>
                <option value="delivered">Delivered</option>
                <option value="out_for_delivery">Out for Delivery / Shipped</option>
                <option value="processing">Processing</option>
                <option value="pending">Pending</option>
                <option value="cancelled">Cancelled</option>
              </select>
            </div>
          </div>

          {/* Sales History Table */}
          {isLoadingSales ? (
            <div className="text-text-secondary text-sm py-12 text-center">Loading sales history...</div>
          ) : (
            <div className="space-y-4">
              <div className="glass-card rounded-2xl overflow-hidden">
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm border-collapse">
                    <thead>
                      <tr className="border-b border-subtle surface-tint text-xs font-medium text-text-secondary uppercase tracking-wider">
                        <th className="py-4 px-6">Order #</th>
                        <th className="py-4 px-6">Customer & Location</th>
                        <th className="py-4 px-6">Purchased Items</th>
                        <th className="py-4 px-6">Total Amount</th>
                        <th className="py-4 px-6">Status</th>
                        <th className="py-4 px-6">Date Placed</th>
                        <th className="py-4 px-6 text-right">Details</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border-panel">
                      {paginatedOrders.map((order) => (
                        <tr key={order.id} className="surface-tint-hover transition-colors">
                          <td className="py-4 px-6 font-mono text-xs text-accent-primary font-medium">
                            {order.order_number}
                          </td>
                          <td className="py-4 px-6">
                            <div className="font-medium text-text-primary">{order.customer_name || "Guest Customer"}</div>
                            <div className="text-xs text-text-secondary flex items-center gap-1 mt-0.5">
                              <MapPin size={11} /> {order.delivery_city || "N/A"}
                            </div>
                          </td>
                          <td className="py-4 px-6">
                            <div className="space-y-1 max-w-xs">
                              {order.items && order.items.length > 0 ? (
                                order.items.map((item, idx) => (
                                  <div key={idx} className="text-xs flex items-center justify-between gap-2">
                                    <span className="text-text-primary truncate">{item.product_name || `Product #${item.product_id}`}</span>
                                    <span className="font-mono text-text-secondary bg-border-panel/40 px-1.5 py-0.5 rounded text-[10px]">
                                      x{item.quantity}
                                    </span>
                                  </div>
                                ))
                              ) : (
                                <span className="text-xs text-text-secondary italic">Standard items</span>
                              )}
                            </div>
                          </td>
                          <td className="py-4 px-6 font-mono font-medium text-emerald-400">
                            ${Number(order.total_amount || 0).toFixed(2)}
                          </td>
                          <td className="py-4 px-6">
                            {getStatusBadge(order.status)}
                          </td>
                          <td className="py-4 px-6 text-xs text-text-secondary font-mono">
                            {order.created_at ? new Date(order.created_at).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' }) : 'Recent'}
                          </td>
                          <td className="py-4 px-6 text-right">
                            <button
                              onClick={() => setSelectedOrder(order)}
                              className="p-1.5 bg-border-panel/30 text-text-secondary hover:text-text-primary rounded-lg transition-colors cursor-pointer inline-flex items-center gap-1 text-xs"
                              title="Inspect Order"
                            >
                              <Eye size={14} />
                              <span className="hidden sm:inline">View</span>
                            </button>
                          </td>
                        </tr>
                      ))}
                      {filteredOrders.length === 0 && (
                        <tr>
                          <td colSpan={7} className="py-8 text-center text-text-secondary text-sm">
                            No orders match your search filter "{salesSearchQuery}".
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Sales Pagination Controls */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pt-2 px-2">
                <div className="text-xs text-text-secondary">
                  Showing <span className="font-medium text-text-primary">{filteredOrders.length > 0 ? (salesCurrentPage - 1) * salesItemsPerPage + 1 : 0}</span> to <span className="font-medium text-text-primary">{Math.min(salesCurrentPage * salesItemsPerPage, filteredOrders.length)}</span> of <span className="font-medium text-text-primary">{filteredOrders.length}</span> orders
                </div>
                <div className="flex items-center gap-2">
                  <button
                    disabled={salesCurrentPage === 1}
                    onClick={() => setSalesCurrentPage((prev) => Math.max(1, prev - 1))}
                    className="p-2 bg-border-panel/20 text-text-secondary hover:text-text-primary border border-border-panel rounded-xl disabled:opacity-30 disabled:cursor-not-allowed transition-colors cursor-pointer flex items-center gap-1 text-xs"
                  >
                    <ChevronLeft size={14} /> Previous
                  </button>
                  <span className="px-3 py-1 text-xs font-mono text-text-secondary bg-border-panel/20 rounded-xl border border-border-panel">
                    Page <strong className="text-text-primary">{salesCurrentPage}</strong> of {salesTotalPages}
                  </span>
                  <button
                    disabled={salesCurrentPage >= salesTotalPages}
                    onClick={() => setSalesCurrentPage((prev) => Math.min(salesTotalPages, prev + 1))}
                    className="p-2 bg-border-panel/20 text-text-secondary hover:text-text-primary border border-border-panel rounded-xl disabled:opacity-30 disabled:cursor-not-allowed transition-colors cursor-pointer flex items-center gap-1 text-xs"
                  >
                    Next <ChevronRight size={14} />
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ────────────────── RECORD NEW SALE MODAL ────────────────── */}
      {isSaleModalOpen && (
        <div className="fixed inset-0 glass-modal-overlay flex items-center justify-center p-4 z-50">
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.25 }}
            className="w-full max-w-lg glass-card rounded-2xl shadow-2xl overflow-hidden p-6 space-y-6 transform-gpu will-change-transform"
          >
            <div className="flex items-center justify-between border-b border-subtle pb-4">
              <div className="flex items-center gap-2">
                <ShoppingCart className="text-emerald-400" size={20} />
                <h3 className="text-xl font-light text-text-primary">Record New Sale Transaction</h3>
              </div>
              <button onClick={() => setIsSaleModalOpen(false)} className="text-text-secondary hover:text-text-primary cursor-pointer">
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleProcessSale} className="space-y-4 text-sm">
              <div>
                <label className="text-xs uppercase tracking-wider text-text-secondary mb-1 block">Select Product to Sell</label>
                <select
                  required
                  value={saleForm.product_id}
                  onChange={(e) => setSaleForm({ ...saleForm, product_id: e.target.value })}
                  className="w-full bg-bg-base border border-border-panel rounded-xl px-3.5 py-2.5 text-text-primary focus:outline-none focus:border-accent-primary cursor-pointer text-xs"
                >
                  {products.map((p) => (
                    <option key={p.id} value={p.id} disabled={p.quantity_on_hand === 0}>
                      {p.name} ({p.sku}) — ${Number(p.unit_price || 0).toFixed(2)} | Stock: {p.quantity_on_hand} units {p.quantity_on_hand === 0 ? "(OUT OF STOCK)" : ""}
                    </option>
                  ))}
                </select>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-xs uppercase tracking-wider text-text-secondary mb-1 block">Quantity Sold</label>
                  <input
                    type="number"
                    min="1"
                    max={selectedProductObj?.quantity_on_hand || 100}
                    required
                    value={saleForm.quantity}
                    onChange={(e) => setSaleForm({ ...saleForm, quantity: Math.max(1, parseInt(e.target.value) || 1) })}
                    className="w-full bg-bg-base border border-border-panel rounded-xl px-3.5 py-2 text-text-primary focus:outline-none focus:border-accent-primary font-mono"
                  />
                </div>
                <div>
                  <label className="text-xs uppercase tracking-wider text-text-secondary mb-1 block">Total Charge</label>
                  <div className="w-full bg-bg-panel/80 border border-border-panel rounded-xl px-3.5 py-2 text-emerald-400 font-mono font-medium text-base">
                    ${((selectedProductObj?.unit_price || 0) * saleForm.quantity).toFixed(2)}
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-xs uppercase tracking-wider text-text-secondary mb-1 block">Customer Name</label>
                  <input
                    type="text"
                    required
                    value={saleForm.customer_name}
                    onChange={(e) => setSaleForm({ ...saleForm, customer_name: e.target.value })}
                    placeholder="Rahul Mehta"
                    className="w-full bg-bg-base border border-border-panel rounded-xl px-3.5 py-2 text-text-primary focus:outline-none focus:border-accent-primary"
                  />
                </div>
                <div>
                  <label className="text-xs uppercase tracking-wider text-text-secondary mb-1 block">Customer Email</label>
                  <input
                    type="email"
                    required
                    value={saleForm.customer_email}
                    onChange={(e) => setSaleForm({ ...saleForm, customer_email: e.target.value })}
                    placeholder="rahul@example.com"
                    className="w-full bg-bg-base border border-border-panel rounded-xl px-3.5 py-2 text-text-primary focus:outline-none focus:border-accent-primary"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-xs uppercase tracking-wider text-text-secondary mb-1 block">Delivery City</label>
                  <input
                    type="text"
                    required
                    value={saleForm.delivery_city}
                    onChange={(e) => setSaleForm({ ...saleForm, delivery_city: e.target.value })}
                    placeholder="Mumbai"
                    className="w-full bg-bg-base border border-border-panel rounded-xl px-3.5 py-2 text-text-primary focus:outline-none focus:border-accent-primary"
                  />
                </div>
                <div>
                  <label className="text-xs uppercase tracking-wider text-text-secondary mb-1 block">Delivery Address</label>
                  <input
                    type="text"
                    required
                    value={saleForm.delivery_address}
                    onChange={(e) => setSaleForm({ ...saleForm, delivery_address: e.target.value })}
                    placeholder="Bandra West, Mumbai"
                    className="w-full bg-bg-base border border-border-panel rounded-xl px-3.5 py-2 text-text-primary focus:outline-none focus:border-accent-primary"
                  />
                </div>
              </div>

              <div className="pt-4 flex justify-end gap-3 border-t border-border-panel">
                <button
                  type="button"
                  onClick={() => setIsSaleModalOpen(false)}
                  className="px-4 py-2 border border-border-panel text-text-secondary rounded-xl hover:text-text-primary cursor-pointer text-xs"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmittingSale}
                  className="px-5 py-2 bg-emerald-600 text-white font-medium rounded-xl hover:bg-emerald-500 transition-colors cursor-pointer text-xs flex items-center gap-1.5"
                >
                  <ShoppingCart size={14} />
                  {isSubmittingSale ? "Processing..." : "Complete Sale & Deduct Stock"}
                </button>
              </div>
            </form>
          </motion.div>
        </div>
      )}

      {/* ────────────────── ORDER INSPECTION MODAL ────────────────── */}
      {selectedOrder && (
        <div className="fixed inset-0 glass-modal-overlay flex items-center justify-center p-4 z-50">
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.25 }}
            className="w-full max-w-2xl glass-card rounded-2xl shadow-2xl overflow-hidden p-6 space-y-6 transform-gpu will-change-transform max-h-[90vh] overflow-y-auto"
          >
            <div className="flex items-center justify-between border-b border-subtle pb-4">
              <div>
                <span className="text-xs uppercase tracking-wider text-text-secondary font-mono">Order Inspection</span>
                <h3 className="text-xl font-light text-text-primary font-mono">{selectedOrder.order_number}</h3>
              </div>
              <button
                onClick={() => setSelectedOrder(null)}
                className="text-text-secondary hover:text-text-primary cursor-pointer p-1 rounded-lg hover:bg-border-panel/30"
              >
                <X size={20} />
              </button>
            </div>

            {/* Customer & Shipping Summary Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
              <div className="p-4 bg-bg-base/60 rounded-xl border border-border-panel space-y-2">
                <div className="font-medium text-text-primary flex items-center gap-1.5">
                  <User size={13} className="text-accent-primary" /> Customer Info
                </div>
                <div className="text-text-secondary space-y-1">
                  <div>Name: <strong className="text-text-primary">{selectedOrder.customer_name || 'N/A'}</strong></div>
                  <div>Email: <strong className="text-text-primary">{selectedOrder.customer_email || 'N/A'}</strong></div>
                  <div>Phone: <strong className="text-text-primary">{selectedOrder.customer_phone || 'N/A'}</strong></div>
                </div>
              </div>

              <div className="p-4 bg-bg-base/60 rounded-xl border border-border-panel space-y-2">
                <div className="font-medium text-text-primary flex items-center gap-1.5">
                  <MapPin size={13} className="text-accent-primary" /> Delivery Destination
                </div>
                <div className="text-text-secondary space-y-1">
                  <div>City: <strong className="text-text-primary">{selectedOrder.delivery_city || 'N/A'}</strong></div>
                  <div>Address: <strong className="text-text-primary">{selectedOrder.delivery_address || 'N/A'}</strong></div>
                  <div>Status: {getStatusBadge(selectedOrder.status)}</div>
                </div>
              </div>
            </div>

            {/* Itemized Order Table */}
            <div>
              <h4 className="text-xs uppercase tracking-wider text-text-secondary mb-2 font-medium">Itemized Breakdown</h4>
              <div className="border border-border-panel rounded-xl overflow-hidden bg-bg-base/40">
                <table className="w-full text-left text-xs border-collapse">
                  <thead>
                    <tr className="border-b border-border-panel surface-tint font-medium text-text-secondary">
                      <th className="py-2.5 px-4">Item</th>
                      <th className="py-2.5 px-4">SKU</th>
                      <th className="py-2.5 px-4 text-center">Qty</th>
                      <th className="py-2.5 px-4 text-right">Unit Price</th>
                      <th className="py-2.5 px-4 text-right">Subtotal</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border-panel">
                    {selectedOrder.items && selectedOrder.items.length > 0 ? (
                      selectedOrder.items.map((item, i) => (
                        <tr key={i}>
                          <td className="py-2.5 px-4 font-medium text-text-primary">{item.product_name || 'Standard Item'}</td>
                          <td className="py-2.5 px-4 font-mono text-text-secondary">{item.product_sku || '-'}</td>
                          <td className="py-2.5 px-4 text-center font-mono">{item.quantity}</td>
                          <td className="py-2.5 px-4 text-right font-mono">${Number(item.unit_price || 0).toFixed(2)}</td>
                          <td className="py-2.5 px-4 text-right font-mono text-text-primary">
                            ${(Number(item.quantity || 0) * Number(item.unit_price || 0)).toFixed(2)}
                          </td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td colSpan={5} className="py-4 text-center text-text-secondary italic">No itemized details attached.</td>
                      </tr>
                    )}
                  </tbody>
                  <tfoot>
                    <tr className="border-t border-border-panel surface-tint font-medium text-sm">
                      <td colSpan={4} className="py-3 px-4 text-right text-text-secondary">Total Amount Paid:</td>
                      <td className="py-3 px-4 text-right font-mono font-bold text-emerald-400">
                        ${Number(selectedOrder.total_amount || 0).toFixed(2)}
                      </td>
                    </tr>
                  </tfoot>
                </table>
              </div>
            </div>

            <div className="pt-2 flex justify-end">
              <button
                onClick={() => setSelectedOrder(null)}
                className="px-5 py-2 bg-border-panel/40 text-text-primary rounded-xl text-xs hover:bg-border-panel transition-colors cursor-pointer"
              >
                Close Receipt
              </button>
            </div>
          </motion.div>
        </div>
      )}

      {/* ────────────────── ADD PRODUCT MODAL ────────────────── */}
      {isAddModalOpen && (
        <div className="fixed inset-0 glass-modal-overlay flex items-center justify-center p-4 z-50">
          <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: 0.25 }} className="w-full max-w-lg glass-card rounded-2xl shadow-2xl overflow-hidden p-6 space-y-6 transform-gpu will-change-transform">
            <div className="flex items-center justify-between border-b border-subtle pb-4">
              <h3 className="text-xl font-light text-text-primary">Add New Product to Catalog</h3>
              <button onClick={() => setIsAddModalOpen(false)} className="text-text-secondary hover:text-text-primary cursor-pointer">
                <X size={20} />
              </button>
            </div>

            {formError && (
              <div className="p-3 bg-red-500/10 border border-red-500/20 text-red-400 text-xs rounded-xl">{formError}</div>
            )}

            <form onSubmit={handleCreateProduct} className="space-y-4 text-sm">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-xs uppercase tracking-wider text-text-secondary mb-1 block">SKU Code</label>
                  <input
                    type="text"
                    required
                    value={newProduct.sku}
                    onChange={(e) => setNewProduct({ ...newProduct, sku: e.target.value })}
                    placeholder="SKU-ELEC-999"
                    className="w-full bg-bg-base border border-border-panel rounded-xl px-3.5 py-2 text-text-primary focus:outline-none focus:border-accent-primary font-mono"
                  />
                </div>
                <div>
                  <label className="text-xs uppercase tracking-wider text-text-secondary mb-1 block">Category</label>
                  <input
                    type="text"
                    required
                    value={newProduct.category}
                    onChange={(e) => setNewProduct({ ...newProduct, category: e.target.value })}
                    placeholder="Electronics"
                    className="w-full bg-bg-base border border-border-panel rounded-xl px-3.5 py-2 text-text-primary focus:outline-none focus:border-accent-primary"
                  />
                </div>
              </div>

              <div>
                <label className="text-xs uppercase tracking-wider text-text-secondary mb-1 block">Product Name</label>
                <input
                  type="text"
                  required
                  value={newProduct.name}
                  onChange={(e) => setNewProduct({ ...newProduct, name: e.target.value })}
                  placeholder="Noise-Canceling Wireless Earbuds"
                  className="w-full bg-bg-base border border-border-panel rounded-xl px-3.5 py-2 text-text-primary focus:outline-none focus:border-accent-primary"
                />
              </div>

              <div className="grid grid-cols-3 gap-4">
                <div>
                  <label className="text-xs uppercase tracking-wider text-text-secondary mb-1 block">Unit Price ($)</label>
                  <input
                    type="number"
                    step="0.01"
                    required
                    value={newProduct.unit_price}
                    onChange={(e) => setNewProduct({ ...newProduct, unit_price: parseFloat(e.target.value) || 0 })}
                    className="w-full bg-bg-base border border-border-panel rounded-xl px-3.5 py-2 text-text-primary focus:outline-none focus:border-accent-primary font-mono"
                  />
                </div>
                <div>
                  <label className="text-xs uppercase tracking-wider text-text-secondary mb-1 block">Initial Stock</label>
                  <input
                    type="number"
                    required
                    value={newProduct.quantity_on_hand}
                    onChange={(e) => setNewProduct({ ...newProduct, quantity_on_hand: parseInt(e.target.value) || 0 })}
                    className="w-full bg-bg-base border border-border-panel rounded-xl px-3.5 py-2 text-text-primary focus:outline-none focus:border-accent-primary font-mono"
                  />
                </div>
                <div>
                  <label className="text-xs uppercase tracking-wider text-text-secondary mb-1 block">Reorder Level</label>
                  <input
                    type="number"
                    required
                    value={newProduct.reorder_point}
                    onChange={(e) => setNewProduct({ ...newProduct, reorder_point: parseInt(e.target.value) || 0 })}
                    className="w-full bg-bg-base border border-border-panel rounded-xl px-3.5 py-2 text-text-primary focus:outline-none focus:border-accent-primary font-mono"
                  />
                </div>
              </div>

              <div className="pt-4 flex justify-end gap-3 border-t border-border-panel">
                <button
                  type="button"
                  onClick={() => setIsAddModalOpen(false)}
                  className="px-4 py-2 border border-border-panel text-text-secondary rounded-xl hover:text-text-primary cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="px-5 py-2 bg-accent-primary text-bg-base font-medium rounded-xl hover:opacity-90 transition-opacity cursor-pointer"
                >
                  {isSubmitting ? "Creating..." : "Save Product"}
                </button>
              </div>
            </form>
          </motion.div>
        </div>
      )}

      {/* ────────────────── EDIT PRODUCT MODAL ────────────────── */}
      {editingProduct && (
        <div className="fixed inset-0 glass-modal-overlay flex items-center justify-center p-4 z-50">
          <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: 0.25 }} className="w-full max-w-lg glass-card rounded-2xl shadow-2xl overflow-hidden p-6 space-y-6 transform-gpu will-change-transform">
            <div className="flex items-center justify-between border-b border-subtle pb-4">
              <h3 className="text-xl font-light text-text-primary">Edit Product: {editingProduct.sku}</h3>
              <button onClick={() => setEditingProduct(null)} className="text-text-secondary hover:text-text-primary cursor-pointer">
                <X size={20} />
              </button>
            </div>

            {formError && (
              <div className="p-3 bg-red-500/10 border border-red-500/20 text-red-400 text-xs rounded-xl">{formError}</div>
            )}

            <form onSubmit={handleUpdateProduct} className="space-y-4 text-sm">
              <div>
                <label className="text-xs uppercase tracking-wider text-text-secondary mb-1 block">Product Name</label>
                <input
                  type="text"
                  required
                  value={editForm.name}
                  onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
                  className="w-full bg-bg-base border border-border-panel rounded-xl px-3.5 py-2 text-text-primary focus:outline-none focus:border-accent-primary"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-xs uppercase tracking-wider text-text-secondary mb-1 block">Category</label>
                  <input
                    type="text"
                    value={editForm.category}
                    onChange={(e) => setEditForm({ ...editForm, category: e.target.value })}
                    className="w-full bg-bg-base border border-border-panel rounded-xl px-3.5 py-2 text-text-primary focus:outline-none focus:border-accent-primary"
                  />
                </div>
                <div>
                  <label className="text-xs uppercase tracking-wider text-text-secondary mb-1 block">Unit Price ($)</label>
                  <input
                    type="number"
                    step="0.01"
                    value={editForm.unit_price}
                    onChange={(e) => setEditForm({ ...editForm, unit_price: parseFloat(e.target.value) || 0 })}
                    className="w-full bg-bg-base border border-border-panel rounded-xl px-3.5 py-2 text-text-primary focus:outline-none focus:border-accent-primary font-mono"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-xs uppercase tracking-wider text-text-secondary mb-1 block">Available Stock (Qty)</label>
                  <input
                    type="number"
                    value={editForm.quantity_on_hand}
                    onChange={(e) => setEditForm({ ...editForm, quantity_on_hand: parseInt(e.target.value) || 0 })}
                    className="w-full bg-bg-base border border-border-panel rounded-xl px-3.5 py-2 text-text-primary focus:outline-none focus:border-accent-primary font-mono"
                  />
                </div>
                <div>
                  <label className="text-xs uppercase tracking-wider text-text-secondary mb-1 block">Reorder Threshold</label>
                  <input
                    type="number"
                    value={editForm.reorder_point}
                    onChange={(e) => setEditForm({ ...editForm, reorder_point: parseInt(e.target.value) || 0 })}
                    className="w-full bg-bg-base border border-border-panel rounded-xl px-3.5 py-2 text-text-primary focus:outline-none focus:border-accent-primary font-mono"
                  />
                </div>
              </div>

              <div className="pt-4 flex justify-end gap-3 border-t border-border-panel">
                <button
                  type="button"
                  onClick={() => setEditingProduct(null)}
                  className="px-4 py-2 border border-border-panel text-text-secondary rounded-xl hover:text-text-primary cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="px-5 py-2 bg-accent-primary text-bg-base font-medium rounded-xl hover:opacity-90 transition-opacity cursor-pointer"
                >
                  {isSubmitting ? "Updating..." : "Update Details"}
                </button>
              </div>
            </form>
          </motion.div>
        </div>
      )}
    </div>
  );
}
