import type { ReactNode } from "react";
import { Breadcrumbs, type BreadcrumbItem } from "./Breadcrumbs";

interface DetailPageHeaderProps {
  breadcrumbs: BreadcrumbItem[];
  title: string;
  badge?: ReactNode;
}

export function DetailPageHeader({ breadcrumbs, title, badge }: DetailPageHeaderProps) {
  return (
    <header className="detail-page-header">
      <Breadcrumbs items={breadcrumbs} />
      <div className="detail-page-header-main">
        <h1>{title}</h1>
        {badge}
      </div>
    </header>
  );
}
