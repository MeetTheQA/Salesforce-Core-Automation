import { redirect } from "next/navigation";

export default async function ProjectScopedFeaturesPage({
  params,
}: {
  params: Promise<{ project: string }>;
}) {
  const { project } = await params;
  redirect(`/projects/${encodeURIComponent(project)}/features`);
}

