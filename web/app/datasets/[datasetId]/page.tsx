import { redirect } from "next/navigation";

export default async function DatasetDetailPage({
  params,
}: {
  params: Promise<{ datasetId: string }>;
}) {
  const { datasetId } = await params;
  redirect(`/datasets/${datasetId}/collections`);
}
