import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { useUserPreferences } from "../settings/UserPreferencesContext";
import { formatDateValue } from "../utils/formatDisplayValue";
import { CommentsIcon } from "./DetailIcons";
import { ExpandableDetailSection } from "./ExpandableDetailSection";

interface RecordCommentsSectionProps {
  resource: string;
  sysId: string;
  canComment: boolean;
  sectionId?: string;
}

export function RecordCommentsSection({
  resource,
  sysId,
  canComment,
  sectionId = "ci-section-comments",
}: RecordCommentsSectionProps) {
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState("");
  const { dateDisplayFormat } = useUserPreferences();

  const { data: comments = [] } = useQuery({
    queryKey: ["comments", resource, sysId],
    queryFn: () => api.listComments(resource, sysId),
  });

  const createMutation = useMutation({
    mutationFn: (comment: string) => api.createComment(resource, sysId, comment),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["comments", resource, sysId] });
      setDraft("");
    },
  });

  return (
    <ExpandableDetailSection
      id={sectionId}
      title="Comments"
      icon={<CommentsIcon size={14} />}
      accent="accent"
      count={comments.length}
    >
      {comments.length === 0 && <p className="empty-state">No comments yet</p>}
      <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
        {comments.map((c) => (
          <li
            key={c.sys_id}
            style={{
              marginBottom: "0.75rem",
              paddingBottom: "0.75rem",
              borderBottom: "1px solid var(--border-subtle)",
            }}
          >
            <p style={{ margin: 0 }}>{c.comment}</p>
            <p className="text-muted text-sm" style={{ margin: "0.25rem 0 0" }}>
              {c.sys_created_on ? formatDateValue(c.sys_created_on, dateDisplayFormat) : ""}
            </p>
          </li>
        ))}
      </ul>
      {canComment && (
        <div style={{ marginTop: "1rem" }}>
          <div className="form-group">
            <label htmlFor="comment-draft">Add comment</label>
            <textarea
              id="comment-draft"
              rows={3}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
            />
          </div>
          <button
            className="btn btn-primary"
            disabled={!draft.trim() || createMutation.isPending}
            onClick={() => createMutation.mutate(draft.trim())}
          >
            Post Comment
          </button>
        </div>
      )}
    </ExpandableDetailSection>
  );
}
