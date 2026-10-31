import { Vector3, type Color, type Material, type Object3D } from "three";

export function createModelColorController(root: Object3D, associations: Map<object, { materials?: number; meshes?: number; primitives?: number }>, json?: { meshes?: Array<{ primitives: Array<{ material?: number }> }> }) {
  const entries = new Map<Material, { material: Material & { color: Color }; original: Color; index: number }>();
  root.traverse((node) => {
    const renderable = node as Object3D & { material?: Material | Material[] };
    if (!renderable.material) return;
    const reference = associations.get(node);
    // GLTFLoader converts line/point materials without retaining their material association.
    const primitiveIndex = reference?.meshes !== undefined && reference.primitives !== undefined
      ? json?.meshes?.[reference.meshes]?.primitives[reference.primitives]?.material : undefined;
    for (const material of [renderable.material].flat()) {
      const colored = material as Material & { color?: Color };
      const index = associations.get(material)?.materials ?? primitiveIndex;
      if (!colored.color?.isColor || !Number.isInteger(index) || entries.has(material)) continue;
      entries.set(material, { material: colored as Material & { color: Color }, original: colored.color.clone(), index: index! });
    }
  });
  return {
    apply(index: number | null, hex?: string) {
      entries.forEach(({ material, original }) => material.color.copy(original));
      if (index === null || !hex || !/^#[\da-f]{6}$/i.test(hex)) return false;
      let matched = false;
      entries.forEach((entry) => {
        if (entry.index !== index) return;
        entry.material.color.set(hex);
        matched = true;
      });
      return matched;
    }
  };
}

export function modelViewDirection(value?: readonly number[] | null): Vector3 {
  if (value?.length === 3 && value.every(Number.isFinite) && Math.hypot(...value) > 1e-8) {
    return new Vector3(value[0], value[1], value[2]).normalize();
  }
  return new Vector3(1.15, 0.8, 1.45).normalize();
}

export function captureModelViewDirection(position: Vector3, target: Vector3): [number, number, number] {
  return modelViewDirection(position.clone().sub(target).toArray()).toArray() as [number, number, number];
}
