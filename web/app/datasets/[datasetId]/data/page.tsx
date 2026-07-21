import { redirect } from "next/navigation";
import { DataBrowser } from "@/components/data/data-browser";

interface DataPageProps {
  params: Promise<{ datasetId: string }>;
  searchParams: Promise<{ collectionId?: string | string[] }>;
}

export default async function DataPage({
  params,
  searchParams,
}: DataPageProps) {
  const { datasetId } = await params;
  const { collectionId } = await searchParams;

  const collectionIdValue = Array.isArray(collectionId)
    ? collectionId[0]
    : collectionId;

  if (!collectionIdValue) {
    redirect(`/datasets/${datasetId}/collections`);
  }

  return (
    <DataBrowser
      datasetId={datasetId}
      collectionId={collectionIdValue}
    />
  );
}
