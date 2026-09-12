import Link from "next/link";
import { ProductWorkspace } from "@/components/ProductWorkspace";
import { getProductSnapshot } from "@/lib/product";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "Product · OpenROAD Studio",
  description: "Live design measurements from the current invocation.",
};

export default function ProductPage() {
  const data = getProductSnapshot();

  return (
    <main className="product-page">
      <header className="product-page-head">
        <div>
          <p className="eyebrow">Product surface</p>
          <h1>{data.title}</h1>
          <p>{data.lead}</p>
          <p className="product-page-rule">{data.rule}</p>
        </div>
        <div className="product-page-links">
          <Link href="/materials/dse/product.md">learn/dse/product.md</Link>
          <span>·</span>
          <code>learn/dse/win_rule.py</code>
          <span>·</span>
          <Link href="/lab">Lab IR and DSE</Link>
        </div>
      </header>
      <ProductWorkspace data={data} />
    </main>
  );
}
