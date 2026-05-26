import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty";
import { Skeleton } from "@/components/ui/skeleton";

function SalesListEmpty({ loading }: { loading: boolean }) {
  if (loading) {
    return (
      <div className="sales-list-skeleton" aria-label="销售单加载中">
        {Array.from({ length: 8 }).map((_, index) => (
          <Skeleton key={index} />
        ))}
      </div>
    );
  }

  return (
    <Empty>
      <EmptyHeader>
        <EmptyTitle>没有销售单</EmptyTitle>
        <EmptyDescription>换个关键词或筛选条件搜索，或者先去开单。</EmptyDescription>
      </EmptyHeader>
    </Empty>
  );
}

export { SalesListEmpty };
