import { useState, useEffect } from "react";
import { Plus, Edit, RefreshCw, Search, Package, AlertTriangle, CheckCircle2, DollarSign, Layers, X } from "lucide-react";
import { fetchProducts, createProduct, updateProduct } from "../api";

export default function ShopManagement({ onTriggerRestock }) {
  const [products, setProducts] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [editingProduct, setEditingProduct] = useState(null);

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
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadProducts();
  }, []);

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
      await loadProducts();
    } catch (err) {
      setFormError(err.response?.data?.detail || "Failed to create product");
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
      await loadProducts();
    } catch (err) {
      setFormError(err.response?.data?.detail || "Failed to update product");
    } finally {
      setIsSubmitting(false);
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

  const filteredProducts = products.filter((p) => {
    const q = searchQuery.toLowerCase().trim();
    if (!q) return true;
    const nameMatch = p.name ? p.name.toLowerCase().includes(q) : false;
    const skuMatch = p.sku ? p.sku.toLowerCase().includes(q) : false;
    const catMatch = p.category ? p.category.toLowerCase().includes(q) : false;
    return nameMatch || skuMatch || catMatch;
  });

  return (
    <div className="space-y-8">
      <header className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-border-panel pb-6">
        <div>
          <h1 className="text-4xl font-light tracking-tight mb-1">Shop Inventory Management</h1>
          <p className="text-text-secondary text-sm">Direct owner control portal for live product catalog and stock adjustments.</p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={loadProducts}
            className="p-2.5 bg-border-panel/20 text-text-secondary hover:text-text-primary rounded-xl border border-border-panel transition-colors cursor-pointer"
            title="Refresh Inventory"
          >
            <RefreshCw size={16} />
          </button>
          <button
            onClick={() => setIsAddModalOpen(true)}
            className="px-4 py-2.5 bg-accent-primary text-bg-base font-medium rounded-xl text-sm hover:opacity-90 transition-opacity flex items-center gap-2 cursor-pointer shadow-lg"
          >
            <Plus size={16} />
            <span>Add New Product</span>
          </button>
        </div>
      </header>

      {/* Search & Filter Bar */}
      <div className="flex items-center justify-between gap-4">
        <div className="relative flex-1 max-w-md">
          <Search size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-text-secondary" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search by SKU, Product Name, or Category..."
            className="w-full bg-border-panel/10 border border-border-panel rounded-xl pl-10 pr-4 py-2.5 text-sm text-text-primary placeholder:text-text-placeholder focus:outline-none focus:border-accent-primary transition-colors"
          />
        </div>
        <div className="text-xs font-mono text-text-secondary">
          Showing <span className="text-text-primary font-medium">{filteredProducts.length}</span> of {products.length} Products
        </div>
      </div>

      {/* Products Table */}
      {isLoading ? (
        <div className="text-text-secondary text-sm py-12 text-center">Loading product catalog...</div>
      ) : (
        <div className="bg-border-panel/10 border border-border-panel rounded-2xl overflow-hidden shadow-xl">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm border-collapse">
              <thead>
                <tr className="border-b border-border-panel bg-border-panel/20 text-xs font-medium text-text-secondary uppercase tracking-wider">
                  <th className="py-4 px-6">SKU</th>
                  <th className="py-4 px-6">Product Details</th>
                  <th className="py-4 px-6">Unit Price</th>
                  <th className="py-4 px-6">Stock Level</th>
                  <th className="py-4 px-6">Reorder Threshold</th>
                  <th className="py-4 px-6">Health Status</th>
                  <th className="py-4 px-6 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border-panel/50">
                {filteredProducts.map((p) => {
                  const isLow = p.quantity_on_hand <= p.reorder_point;
                  const isCritical = p.quantity_on_hand === 0;

                  return (
                    <tr key={p.id} className="hover:bg-border-panel/10 transition-colors">
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
                            onClick={() => openEditModal(p)}
                            className="p-1.5 bg-border-panel/30 text-text-secondary hover:text-text-primary rounded-lg transition-colors cursor-pointer"
                            title="Edit Product"
                          >
                            <Edit size={15} />
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
      )}

      {/* Add Product Modal */}
      {isAddModalOpen && (
        <div className="fixed inset-0 bg-bg-base/80 backdrop-blur-md flex items-center justify-center p-4 z-50">
          <div className="w-full max-w-lg bg-bg-panel border border-border-panel rounded-2xl shadow-2xl overflow-hidden p-6 space-y-6">
            <div className="flex items-center justify-between border-b border-border-panel pb-4">
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
                  placeholder="Noise-Cancelling Wireless Earbuds"
                  className="w-full bg-bg-base border border-border-panel rounded-xl px-3.5 py-2 text-text-primary focus:outline-none focus:border-accent-primary"
                />
              </div>

              <div className="grid grid-cols-3 gap-4">
                <div>
                  <label className="text-xs uppercase tracking-wider text-text-secondary mb-1 block">Unit Price ($)</label>
                  <input
                    type="number"
                    step="0.01"
                    value={newProduct.unit_price}
                    onChange={(e) => setNewProduct({ ...newProduct, unit_price: parseFloat(e.target.value) || 0 })}
                    className="w-full bg-bg-base border border-border-panel rounded-xl px-3.5 py-2 text-text-primary focus:outline-none focus:border-accent-primary font-mono"
                  />
                </div>
                <div>
                  <label className="text-xs uppercase tracking-wider text-text-secondary mb-1 block">Initial Stock</label>
                  <input
                    type="number"
                    value={newProduct.quantity_on_hand}
                    onChange={(e) => setNewProduct({ ...newProduct, quantity_on_hand: parseInt(e.target.value) || 0 })}
                    className="w-full bg-bg-base border border-border-panel rounded-xl px-3.5 py-2 text-text-primary focus:outline-none focus:border-accent-primary font-mono"
                  />
                </div>
                <div>
                  <label className="text-xs uppercase tracking-wider text-text-secondary mb-1 block">Reorder Point</label>
                  <input
                    type="number"
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
          </div>
        </div>
      )}

      {/* Edit Product Modal */}
      {editingProduct && (
        <div className="fixed inset-0 bg-bg-base/80 backdrop-blur-md flex items-center justify-center p-4 z-50">
          <div className="w-full max-w-lg bg-bg-panel border border-border-panel rounded-2xl shadow-2xl overflow-hidden p-6 space-y-6">
            <div className="flex items-center justify-between border-b border-border-panel pb-4">
              <div>
                <h3 className="text-xl font-light text-text-primary">Edit Product Details</h3>
                <p className="text-xs text-text-secondary font-mono">SKU: {editForm.sku}</p>
              </div>
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
          </div>
        </div>
      )}
    </div>
  );
}
