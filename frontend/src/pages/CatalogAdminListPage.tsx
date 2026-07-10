import { FormEvent, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { usePageHeader } from "../components/PageHeaderContext";
import "./CatalogPages.css";

export function CatalogAdminListPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [shortDescription, setShortDescription] = useState("");
  const [error, setError] = useState("");

  const { data, isLoading, error: loadError } = useQuery({
    queryKey: ["catalog-admin-items"],
    queryFn: () => api.adminListCatalogItems(),
  });

  const createMutation = useMutation({
    mutationFn: () =>
      api.adminCreateCatalogItem({
        name,
        short_description: shortDescription,
        description: "",
        price: "0",
      }),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ["catalog-admin-items"] });
      queryClient.invalidateQueries({ queryKey: ["catalog-items"] });
      navigate(`/catalog/admin/${res.result.sys_id}`);
    },
    onError: (err: Error) => setError(err.message),
  });

  const headerActions = useMemo(
    () => (
      <Link to="/catalog" className="btn btn-primary">
        Browse
      </Link>
    ),
    []
  );

  usePageHeader({
    breadcrumbs: [
      { label: "Service Catalog", to: "/catalog" },
      { label: "Manage" },
    ],
    actions: headerActions,
  });

  function onCreate(event: FormEvent) {
    event.preventDefault();
    if (!name.trim()) {
      setError("Name is required");
      return;
    }
    createMutation.mutate();
  }

  if (isLoading) return <p className="empty-state">Loading…</p>;
  if (loadError) return <p className="error">{(loadError as Error).message}</p>;

  const items = data?.result || [];

  return (
    <div className="catalog-admin-list">
      <div className="card" style={{ padding: 0, overflow: "hidden" }}>
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Category</th>
              <th>Active</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {items.length === 0 ? (
              <tr>
                <td colSpan={4} className="empty-state">
                  No catalog items yet
                </td>
              </tr>
            ) : (
              items.map((item) => (
                <tr key={item.sys_id}>
                  <td>{item.name}</td>
                  <td>{item.category || "—"}</td>
                  <td>{item.active === false ? "No" : "Yes"}</td>
                  <td>
                    <Link to={`/catalog/admin/${item.sys_id}`} className="btn btn-secondary btn-sm">
                      Edit
                    </Link>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <div className="card">
        <form onSubmit={onCreate} className="catalog-builder-form">
          <div className="section-header-row">
            <h2 className="section-title" style={{ marginBottom: 0 }}>New Catalog Item</h2>
            <button type="submit" className="btn btn-primary" disabled={createMutation.isPending}>
              Create
            </button>
          </div>
          <div className="catalog-form-grid">
            <div className="form-group">
              <label htmlFor="new-item-name">Name</label>
              <input
                id="new-item-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </div>
            <div className="form-group">
              <label htmlFor="new-item-short">Short Description</label>
              <input
                id="new-item-short"
                value={shortDescription}
                onChange={(e) => setShortDescription(e.target.value)}
              />
            </div>
          </div>
          {error ? <p className="error">{error}</p> : null}
        </form>
      </div>
    </div>
  );
}
