import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { usePageHeader } from "../components/PageHeaderContext";
import { useAuth } from "../auth/AuthContext";
import { useMemo } from "react";
import "./CatalogPages.css";

export function CatalogBrowsePage() {
  const { hasPermission } = useAuth();
  const canAdmin = hasPermission("records.*.write");

  const headerActions = useMemo(
    () =>
      canAdmin ? (
        <Link to="/catalog/admin" className="btn btn-primary">
          Manage
        </Link>
      ) : null,
    [canAdmin]
  );

  usePageHeader({
    breadcrumbs: [{ label: "Service Catalog" }],
    actions: headerActions,
  });

  const { data, isLoading, error } = useQuery({
    queryKey: ["catalog-items"],
    queryFn: () => api.listCatalogItems(),
  });

  if (isLoading) return <p className="empty-state">Loading catalog…</p>;
  if (error) return <p className="error">{(error as Error).message}</p>;

  const items = data?.result || [];

  return (
    <div className="catalog-browse">
      <p className="catalog-browse-intro">Browse available services and submit requests.</p>
        {items.length === 0 ? (
          <p className="empty-state">No catalog items yet</p>
        ) : (
        <div className="catalog-card-grid">
          {items.map((item) => (
            <Link key={item.sys_id} to={`/catalog/${item.sys_id}`} className="catalog-card">
              <h3>{item.name}</h3>
              <p>{item.short_description || "No description"}</p>
              {item.category ? <span className="catalog-card-meta">{item.category}</span> : null}
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
