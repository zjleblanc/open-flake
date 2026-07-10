import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { ConfirmDialog } from "./ConfirmDialog";
import "./Layout.css";

interface RecordDeleteButtonProps {
  resource: string;
  sysId: string;
  recordLabel: string;
  listPath: string;
}

export function RecordDeleteButton({
  resource,
  sysId,
  recordLabel,
  listPath,
}: RecordDeleteButtonProps) {
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const deleteMutation = useMutation({
    mutationFn: () => api.deleteRecord(resource, sysId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["records", resource] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      navigate(listPath);
    },
    onError: (deleteError: Error) => {
      setError(deleteError.message || "Failed to delete record.");
    },
  });

  return (
    <>
      <button
        type="button"
        className="btn btn-danger-solid"
        onClick={() => {
          setError(null);
          setConfirmOpen(true);
        }}
        disabled={deleteMutation.isPending}
      >
        Delete
      </button>
      <ConfirmDialog
        open={confirmOpen}
        title="Delete record"
        message={`Are you sure you want to permanently delete "${recordLabel}"? This action cannot be undone.`}
        error={error}
        onConfirm={() => deleteMutation.mutate()}
        onCancel={() => {
          setError(null);
          setConfirmOpen(false);
        }}
        isPending={deleteMutation.isPending}
      />
    </>
  );
}
