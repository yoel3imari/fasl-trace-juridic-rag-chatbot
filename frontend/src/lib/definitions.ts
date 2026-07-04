import { z } from "zod";

// ── Document Schemas ──────────────────────────────────────────────
export const documentSchema = z.object({
  filename: z.string().min(1, "Filename is required"),
  language: z.enum(["en", "fr", "ar"]).default("en"),
});

export const documentUploadSchema = z.object({
  file: z.instanceof(File).refine(
    (file) => file.size > 0,
    "File must not be empty"
  ).refine(
    (file) => file.size <= 50 * 1024 * 1024,
    "File size must not exceed 50MB"
  ).refine(
    (file) => file.type === "application/pdf",
    "File must be a PDF"
  ),
  language: z.enum(["en", "fr", "ar"]).default("en"),
});

// ── Collection Schemas ─────────────────────────────────────────────
export const collectionSchema = z.object({
  name: z.string().min(1, "Collection name is required").max(255, "Name too long"),
});

// ── LLM Provider Schemas ───────────────────────────────────────────
export const llmProviderSchema = z.object({
  provider_type: z.enum(["openai", "anthropic", "ollama"], {
    message: "Provider type is required",
  }),
  base_url: z.string().url("Must be a valid URL").optional().or(z.literal("")),
  api_version: z.string().optional(),
});

export const apiKeySchema = z.object({
  api_key: z.string().min(1, "API key is required").max(4096, "API key too long"),
});

// ── Model Assignment Schemas ───────────────────────────────────────
export const modelAssignmentSchema = z.object({
  provider_id: z.string().uuid("Invalid provider ID"),
  model_name: z.string().min(1, "Model name is required").max(255, "Model name too long"),
  system_function: z.enum(["retrieval", "generation", "evaluation"], {
    message: "System function is required",
  }),
});

// ── Auth Schemas (for Supabase login forms) ─────────────────────────
export const loginSchema = z.object({
  email: z.string().email("Invalid email address"),
  password: z.string().min(1, "Password is required"),
});

export const registerSchema = z.object({
  email: z.string().email("Invalid email address"),
  password: z
    .string()
    .min(8, "Password must be at least 8 characters")
    .refine((password) => /[A-Z]/.test(password), {
      message: "Password must contain at least one uppercase letter",
    })
    .refine((password) => /[!@#$%^&*(),.?":{}|<>]/.test(password), {
      message: "Password must contain at least one special character",
    }),
  passwordConfirm: z.string(),
}).refine((data) => data.password === data.passwordConfirm, {
  message: "Passwords must match",
  path: ["passwordConfirm"],
});

// ── Type exports ───────────────────────────────────────────────────
export type DocumentFormData = z.infer<typeof documentSchema>;
export type DocumentUploadFormData = z.infer<typeof documentUploadSchema>;
export type CollectionFormData = z.infer<typeof collectionSchema>;
export type LLMProviderFormData = z.infer<typeof llmProviderSchema>;
export type ApiKeyFormData = z.infer<typeof apiKeySchema>;
export type ModelAssignmentFormData = z.infer<typeof modelAssignmentSchema>;
export type LoginFormData = z.infer<typeof loginSchema>;
export type RegisterFormData = z.infer<typeof registerSchema>;
