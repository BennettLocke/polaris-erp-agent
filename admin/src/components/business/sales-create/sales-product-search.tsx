import { Search } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import type { ProductSearchProps } from "./types";
import {
  inputNoWheel,
  money,
  productColorCount,
  productDisplaySpec,
  productDisplayTitle,
  productVariants
} from "./utils";

function SalesProductSearch({
  productKeyword,
  productResults,
  lineQty,
  loading,
  addedProductIds = [],
  onKeywordChange,
  onQtyChange,
  onSearchProducts,
  onAddLine
}: ProductSearchProps) {
  const addedSet = new Set(addedProductIds);

  return (
    <div className="sales-create-product">
      <div className="sales-create-product-search">
        <Input
          value={productKeyword}
          placeholder="输入礼盒名称，回车搜索"
          onChange={(event) => onKeywordChange(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") onSearchProducts();
          }}
        />
        <Input
          aria-label="加入数量"
          type="number"
          min="1"
          value={lineQty}
          onWheel={inputNoWheel}
          onChange={(event) => onQtyChange(Math.max(1, Number(event.target.value || 1)))}
        />
        <Button variant="outline" type="button" onClick={onSearchProducts}>
          <Search data-icon="inline-start" /> 搜索商品
        </Button>
      </div>

      {loading === "product" ? (
        <Empty className="sales-create-inline-empty">
          <EmptyHeader>
            <EmptyTitle>商品搜索中</EmptyTitle>
            <EmptyDescription>正在按名称、分类和颜色搜索。</EmptyDescription>
          </EmptyHeader>
        </Empty>
      ) : null}

      {productResults.length ? (
        <div className="sales-create-product-results" aria-label="商品搜索结果">
          {productResults.map((product) => (
            <article className="sales-create-product-card" key={product.id || product.product_id}>
              <header>
                <div>
                  <strong>{productDisplayTitle(product)}</strong>
                  <span>{[product.product_category_text, product.piece_text ? `件规：${product.piece_text}` : ""].filter(Boolean).join(" · ")}</span>
                </div>
                <Badge variant="outline">{productColorCount(product)} 个颜色</Badge>
              </header>
              <div className="sales-create-variant-list">
                {productVariants(product).map((variant) => {
                  const variantId = Number(variant.id || variant.product_id || product.id || product.product_id || 0);
                  const alreadyAdded = addedSet.has(variantId);
                  const stockLabel = Number(variant.is_stock_item ?? product.is_stock_item ?? 1) ? "扣库存" : "不扣库存";
                  return (
                    <Button
                      type="button"
                      variant={alreadyAdded ? "secondary" : "outline"}
                      className={cn("sales-create-variant", alreadyAdded && "is-selected")}
                      key={`${product.id || product.product_id}-${variantId}-${productDisplaySpec(variant)}`}
                      disabled={loading === `line-${variantId}`}
                      onClick={() => onAddLine(product, variant)}
                    >
                      <strong>{productDisplaySpec(variant)}</strong>
                      <span>{money(variant.price || variant.min_price || product.price || 0)} · {alreadyAdded ? "已加入" : stockLabel}</span>
                    </Button>
                  );
                })}
              </div>
            </article>
          ))}
        </div>
      ) : null}
    </div>
  );
}

export { SalesProductSearch };
