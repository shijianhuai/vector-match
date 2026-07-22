import { SearchPanel } from "@/components/search/search-panel";

export default async function DatasetSearchPage({
  params,
}: {
  params: Promise<{ datasetId: string }>;
}) {
  const { datasetId } = await params;
  return <SearchPanel datasetId={datasetId} />;
}
