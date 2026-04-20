-- =========================================================================
-- Row-Level Security (RLS) Baseline Policies
-- =========================================================================
-- These policies enforce tenant isolation using the Supabase JWT `sub` claim.
-- auth.uid() returns the authenticated user's UUID from the JWT.
--
-- Apply after running Alembic migrations:
--   psql $DATABASE_URL -f supabase/policies/rls_baseline.sql
-- =========================================================================

-- ── Documents ────────────────────────────────────────────────────────────

ALTER TABLE documents ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view their own documents"
    ON documents FOR SELECT
    USING (user_id = auth.uid());

CREATE POLICY "Users can insert their own documents"
    ON documents FOR INSERT
    WITH CHECK (user_id = auth.uid());

CREATE POLICY "Users can update their own documents"
    ON documents FOR UPDATE
    USING (user_id = auth.uid())
    WITH CHECK (user_id = auth.uid());

CREATE POLICY "Users can delete their own documents"
    ON documents FOR DELETE
    USING (user_id = auth.uid());

-- ── Collections ──────────────────────────────────────────────────────────

ALTER TABLE collections ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view their own collections"
    ON collections FOR SELECT
    USING (user_id = auth.uid());

CREATE POLICY "Users can insert their own collections"
    ON collections FOR INSERT
    WITH CHECK (user_id = auth.uid());

CREATE POLICY "Users can update their own collections"
    ON collections FOR UPDATE
    USING (user_id = auth.uid())
    WITH CHECK (user_id = auth.uid());

CREATE POLICY "Users can delete their own collections"
    ON collections FOR DELETE
    USING (user_id = auth.uid());

-- ── Document-Collection Junction ─────────────────────────────────────────
-- Junction table access is implicitly controlled via the parent table policies.
-- Users can only associate documents they own with collections they own.

ALTER TABLE document_collections ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can manage their document-collection associations"
    ON document_collections FOR ALL
    USING (
        EXISTS (
            SELECT 1 FROM documents d WHERE d.id = document_id AND d.user_id = auth.uid()
        )
        AND
        EXISTS (
            SELECT 1 FROM collections c WHERE c.id = collection_id AND c.user_id = auth.uid()
        )
    );
