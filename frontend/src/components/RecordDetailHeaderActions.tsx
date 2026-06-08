import { getRecordPermissions } from "../api/client";
import { RecordDeleteButton } from "./RecordDeleteButton";
import { RecordSharePopover } from "./RecordSharePopover";
import "./Layout.css";

interface RecordDetailHeaderActionsProps {
  resource: string;
  sysId: string;
  record: Record<string, unknown>;
  recordLabel: string;
  listPath: string;
  canWrite: boolean;
}

export function RecordDetailHeaderActions({
  resource,
  sysId,
  record,
  recordLabel,
  listPath,
  canWrite,
}: RecordDetailHeaderActionsProps) {
  const permissions = getRecordPermissions(record);

  if (!permissions.read) return null;

  return (
    <>
      <RecordSharePopover resource={resource} sysId={sysId} record={record} canWrite={canWrite} />
      {permissions.delete && (
        <RecordDeleteButton
          resource={resource}
          sysId={sysId}
          recordLabel={recordLabel}
          listPath={listPath}
        />
      )}
    </>
  );
}
