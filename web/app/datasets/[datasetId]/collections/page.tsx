import { CollectionBrowser } from "@/components/collections/collection-browser";

export default async function CollectionsPage({
  params,
  searchParams,
}: {
  params: Promise<{ datasetId: string }>;
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}) {
  const { datasetId } = await params;
  const rawParentId = (await searchParams).parentId;
  const parentId =
    typeof rawParentId === "string" ? rawParentId : null;

  return (
    <CollectionBrowser
      key={parentId ?? "root"}
      datasetId={datasetId}
      parentId={parentId}
    />
  );
}
