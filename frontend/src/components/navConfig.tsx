import type { ReactNode } from 'react';
import {
  AccessIcon,
  CatalogIcon,
  ChangeIcon,
  ConfigurationItemIcon,
  DashboardIcon,
  IncidentIcon,
  IntegrationsIcon,
  ProblemIcon,
  RequestedItemIcon,
  RequestIcon,
  SecretIcon,
  SettingsIcon,
  TaskIcon,
  UsersIcon,
  WebhookIcon,
} from './NavIcons';
import { HierarchyIcon } from './DetailIcons';

export type NavLeaf = {
  to: string;
  label: string;
  icon: ReactNode;
  permission?: string;
};

export type NavGroup = {
  id: string;
  label: string;
  icon: ReactNode;
  to?: string;
  permission?: string;
  children: NavLeaf[];
};

export type NavEntry = NavLeaf | NavGroup;

export function isNavGroup(entry: NavEntry): entry is NavGroup {
  return 'children' in entry;
}

/**
 * Full navigation tree for OpenFlake. `to` doubles as the stable identifier
 * used for pinning favorites (see `UserPreferences.pinnedNavItems`) — every
 * independently-navigable item (leaf or group-with-`to`) can be favorited.
 * Groups without a `to` (Integrations, Access) are pure containers: they
 * have no page of their own and cannot be pinned directly, only surfaced
 * in the sidebar when one of their children is favorited.
 */
export const NAV: NavEntry[] = [
  { to: '/', label: 'Dashboard', icon: <DashboardIcon /> },
  {
    id: 'catalog',
    label: 'Service Catalog',
    icon: <CatalogIcon />,
    to: '/catalog',
    children: [
      { to: '/requests', label: 'Requests', icon: <RequestIcon /> },
      { to: '/requested-items', label: 'Requested Items', icon: <RequestedItemIcon /> },
      { to: '/catalog-tasks', label: 'Catalog Tasks', icon: <TaskIcon /> },
    ],
  },
  { to: '/incidents', label: 'Incidents', icon: <IncidentIcon /> },
  { to: '/problems', label: 'Problems', icon: <ProblemIcon /> },
  { to: '/changes', label: 'Changes', icon: <ChangeIcon /> },
  {
    to: '/configuration-items',
    label: 'Configuration Items',
    icon: <ConfigurationItemIcon />,
  },
  {
    id: 'integrations',
    label: 'Integrations',
    icon: <IntegrationsIcon />,
    children: [
      { to: '/integrations/webhooks', label: 'Webhooks', icon: <WebhookIcon /> },
      {
        to: '/integrations/secrets',
        label: 'Secrets',
        icon: <SecretIcon />,
        permission: 'secrets.read',
      },
    ],
  },
  {
    id: 'access',
    label: 'Access',
    icon: <AccessIcon />,
    permission: 'users.read',
    children: [
      { to: '/access/users', label: 'Users', icon: <UsersIcon /> },
      {
        to: '/access/groups',
        label: 'Groups',
        icon: <HierarchyIcon />,
        permission: 'groups.read',
      },
    ],
  },
  { to: '/settings', label: 'Settings', icon: <SettingsIcon /> },
];
