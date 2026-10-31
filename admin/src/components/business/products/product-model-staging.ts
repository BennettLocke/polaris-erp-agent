export function queueStagedModelUploads(staged: Set<number>, cleanup: Set<number>, keepId?: number) {
  for (const id of staged) if (id !== keepId) cleanup.add(id);
  staged.clear();
}

export async function releaseStagedModelUploads(
  staged: Set<number>,
  remove: (id: number) => Promise<{ storage_deleted: boolean }>,
  keepId?: number
) {
  if (keepId !== undefined) staged.delete(keepId);
  return Promise.allSettled([...staged].map(async (id) => {
    const result = await remove(id);
    if (result.storage_deleted) staged.delete(id);
  }));
}
