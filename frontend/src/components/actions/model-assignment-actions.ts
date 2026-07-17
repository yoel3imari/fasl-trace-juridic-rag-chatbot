"use server";

import { revalidatePath } from "next/cache";
import { createClient } from "@/lib/supabase-server";
import {
  listModelAssignments,
  createModelAssignment,
  deleteModelAssignment,
  getModelAssignment,
  updateModelAssignment,
} from "@/app/clientService";
import { modelAssignmentSchema } from "@/lib/definitions";

async function getAuthHeaders() {
  const supabase = await createClient();
  const { data: { session } } = await supabase.auth.getSession();
  if (!session?.access_token) return null;
  return { Authorization: `Bearer ${session.access_token}` };
}

export async function fetchAssignments(
  skip: number = 0,
  limit: number = 50,
  systemFunction?: string
) {
  const headers = await getAuthHeaders();
  if (!headers) return { error: "Not authenticated" };

  const query: Record<string, any> = { skip, limit };
  if (systemFunction) query.system_function = systemFunction;

  const { data, error } = await listModelAssignments({
    headers,
    query,
  });
  if (error) return { error: String(error) };
  return { data };
}

export async function createAssignmentAction(prevState: unknown, formData: FormData) {
  const headers = await getAuthHeaders();
  if (!headers) return { error: "Not authenticated" };

  const validated = modelAssignmentSchema.safeParse({
    provider_id: formData.get("provider_id"),
    model_name: formData.get("model_name"),
    system_function: formData.get("system_function"),
  });
  if (!validated.success) {
    return { errors: validated.error.flatten().fieldErrors };
  }

  const { data, error } = await createModelAssignment({
    headers,
    body: validated.data,
  });
  if (error) return { error: String(error) };
  revalidatePath("/dashboard");
  return { data };
}

export async function updateAssignmentAction(assignmentId: string, formData: FormData) {
  const headers = await getAuthHeaders();
  if (!headers) return { error: "Not authenticated" };

  const body: Record<string, any> = {};
  const modelName = formData.get("model_name");
  const isActive = formData.get("is_active");

  if (modelName !== null) body.model_name = modelName;
  if (isActive !== null) body.is_active = isActive === "true";

  const { data, error } = await updateModelAssignment({
    headers,
    path: { assignment_id: assignmentId },
    body,
  });
  if (error) return { error: String(error) };
  revalidatePath("/dashboard");
  return { data };
}

export async function deleteAssignmentAction(assignmentId: string) {
  const headers = await getAuthHeaders();
  if (!headers) return { error: "Not authenticated" };

  const { error } = await deleteModelAssignment({
    headers,
    path: { assignment_id: assignmentId },
  });
  if (error) return { error: String(error) };
  revalidatePath("/dashboard");
}
