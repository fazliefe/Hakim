import { redirect } from "next/navigation";

export default async function KamuPage({
  searchParams,
}: {
  searchParams: Promise<{ kalip?: string }>;
}) {
  const params = await searchParams;
  const kalip = params.kalip?.trim();
  redirect(kalip ? `/evrak?kalip=${encodeURIComponent(kalip)}` : "/evrak");
}
