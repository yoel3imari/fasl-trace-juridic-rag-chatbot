/**
 * Smoke tests for server actions.
 * These verify the actions exist and can be imported.
 * Full integration tests would require a running backend.
 */

describe("Server Actions", () => {
  describe("Document Actions", () => {
    it("should export document action functions", async () => {
      const actions = await import("@/components/actions/document-actions");
      expect(actions.fetchDocuments).toBeDefined();
      expect(actions.uploadDocumentAction).toBeDefined();
      expect(actions.processDocumentAction).toBeDefined();
      expect(actions.fetchIngestionStatus).toBeDefined();
    });
  });

  describe("Collection Actions", () => {
    it("should export collection action functions", async () => {
      const actions = await import("@/components/actions/collection-actions");
      expect(actions.fetchCollections).toBeDefined();
      expect(actions.createCollectionAction).toBeDefined();
      expect(actions.deleteCollectionAction).toBeDefined();
    });
  });

  describe("LLM Provider Actions", () => {
    it("should export provider action functions", async () => {
      const actions = await import("@/components/actions/llm-provider-actions");
      expect(actions.fetchProviders).toBeDefined();
      expect(actions.createProviderAction).toBeDefined();
      expect(actions.updateProviderAction).toBeDefined();
      expect(actions.deleteProviderAction).toBeDefined();
      expect(actions.setApiKeyAction).toBeDefined();
      expect(actions.deleteApiKeyAction).toBeDefined();
    });
  });

  describe("Model Assignment Actions", () => {
    it("should export assignment action functions", async () => {
      const actions = await import("@/components/actions/model-assignment-actions");
      expect(actions.fetchAssignments).toBeDefined();
      expect(actions.createAssignmentAction).toBeDefined();
      expect(actions.updateAssignmentAction).toBeDefined();
      expect(actions.deleteAssignmentAction).toBeDefined();
    });
  });
});

describe("Zod Schemas", () => {
  it("should validate valid document input", () => {
    const { documentSchema } = require("@/lib/definitions");
    const result = documentSchema.safeParse({
      filename: "test.pdf",
      language: "en",
    });
    expect(result.success).toBe(true);
  });

  it("should reject invalid document input", () => {
    const { documentSchema } = require("@/lib/definitions");
    const result = documentSchema.safeParse({
      filename: "",
      language: "invalid",
    });
    expect(result.success).toBe(false);
  });

  it("should validate valid collection input", () => {
    const { collectionSchema } = require("@/lib/definitions");
    const result = collectionSchema.safeParse({ name: "My Collection" });
    expect(result.success).toBe(true);
  });

  it("should reject empty collection name", () => {
    const { collectionSchema } = require("@/lib/definitions");
    const result = collectionSchema.safeParse({ name: "" });
    expect(result.success).toBe(false);
  });

  it("should validate valid login input", () => {
    const { loginSchema } = require("@/lib/definitions");
    const result = loginSchema.safeParse({
      email: "user@example.com",
      password: "password123",
    });
    expect(result.success).toBe(true);
  });

  it("should reject invalid email in login", () => {
    const { loginSchema } = require("@/lib/definitions");
    const result = loginSchema.safeParse({
      email: "not-an-email",
      password: "password123",
    });
    expect(result.success).toBe(false);
  });
});
