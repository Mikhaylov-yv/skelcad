// 3D-окно: GLB сборки, подсветка узлов, затенение остального, разрез плоскостью, стандартные виды (Z вверх, как в render.py).
import { Component, Suspense, useEffect, useMemo, type ReactNode } from "react";
import { Canvas, useThree } from "@react-three/fiber";
import { OrbitControls, useGLTF, Grid } from "@react-three/drei";
import * as THREE from "three";
import type { OrbitControls as OrbitControlsImpl } from "three-stdlib";
import { S } from "../strings";

export type ViewName = "main" | "left" | "top" | "iso";
export type ClipAxis = "x" | "y" | "z";

export interface Overlay {
  baseUrl: string; // модель «было» (родительский коммит)
  changed: string[]; // узлы, которые изменились: в «стало» — красные, в «было» — синие; остальные серые
  mix: number; // 0 — только «было», 1 — только «стало»
}

export interface Pin {
  id: string;
  point: [number, number, number]; // мм, в координатах модели (Z вверх)
  resolved?: boolean;
}

export interface ViewerProps {
  url: string;
  selected: string[];
  dim: boolean;
  clip: { on: boolean; axis: ClipAxis; pos: number }; // pos 0..1 вдоль габарита
  view: { name: ViewName; nonce: number }; // nonce — чтобы повторный клик по тому же виду сработал
  overlay?: Overlay;
  pins?: Pin[];
  onNodes?: (topLevel: string[]) => void;
  onPick?: (node: string | null, point?: [number, number, number]) => void;
  onError?: (message: string) => void;
}

const BASE = new THREE.Color("#9aa3ad");
const HILITE = new THREE.Color("#e5541e");
const WAS = new THREE.Color("#2f6fd6"); // Onshape: синий — было
const NOW = new THREE.Color("#d63a2f"); // красный — стало

/** Как красить узел: цвет и прозрачность; null — не показывать. */
export type Paint = (top: string | null) => { color: THREE.Color; opacity: number } | null;

export function paintSelection(selected: string[], dim: boolean): Paint {
  const sel = new Set(selected);
  return (top) => {
    const hit = top !== null && sel.has(top);
    if (hit) return { color: HILITE, opacity: 1 };
    return { color: BASE, opacity: sel.size > 0 && dim ? 0.18 : 1 };
  };
}

export function paintOverlay(changed: string[], mix: number, side: "was" | "now"): Paint {
  const ch = new Set(changed);
  return (top) => {
    const hit = top !== null && ch.has(top);
    if (side === "now") return hit ? { color: NOW, opacity: Math.max(mix, 0.05) } : { color: BASE, opacity: 1 };
    return hit ? { color: WAS, opacity: Math.max(1 - mix, 0.05) } : null;
  };
}

// Направления глаз как в render.py: main (-X), left (+Y), top (+Z), iso.
const EYES: Record<ViewName, [number, number, number]> = {
  main: [-1, 0, 0],
  left: [0, 1, 0],
  top: [0, 0, 1],
  iso: [-1, 1, 0.8],
};

function topLevelName(obj: THREE.Object3D, root: THREE.Object3D): string | null {
  let o: THREE.Object3D | null = obj;
  while (o && o.parent && o.parent !== root) o = o.parent;
  return o && o !== root ? o.name : null;
}

/** Группа, чьи дети — сущности модели: GLB обёрнут в узел сборки (A_fork → base_plate, cheek_L, …). */
function entityGroup(scene: THREE.Object3D): THREE.Object3D {
  let g = scene;
  while (g.children.length === 1 && g.children[0].children.length > 0) g = g.children[0];
  return g;
}

interface ModelProps {
  url: string;
  paint: Paint;
  clip: ViewerProps["clip"];
  view?: ViewerProps["view"];
  primary: boolean;
  pins?: Pin[];
  onNodes?: ViewerProps["onNodes"];
  onPick?: ViewerProps["onPick"];
}

function diag(box: THREE.Box3): number {
  return box.getSize(new THREE.Vector3()).length();
}

function Model({ url, paint, clip, view, primary, pins, onNodes, onPick }: ModelProps) {
  const { scene } = useGLTF(url);
  const cloned = useMemo(() => {
    const c = scene.clone(true);
    // glTF хранит метры; интерфейс работает в мм (сетка 50 мм, разрез по габариту). Модель мельче 10 единиц — метры.
    const diag = new THREE.Box3().setFromObject(c).getSize(new THREE.Vector3()).length();
    if (diag > 0 && diag < 10) c.scale.setScalar(1000);
    // glTF — Y вверх: экспорт повернул модель (x, y, z) → (x, z, −y). Возвращаем Z вверх, как в модели и render.py.
    c.rotation.x = Math.PI / 2;
    c.updateMatrixWorld(true);
    return c;
  }, [scene]);
  const root = useMemo(() => entityGroup(cloned), [cloned]);
  const controls = useThree((s) => s.controls) as OrbitControlsImpl | null;
  const camera = useThree((s) => s.camera) as THREE.PerspectiveCamera;
  const box = useMemo(() => new THREE.Box3().setFromObject(cloned), [cloned]);

  useEffect(() => {
    if (primary) onNodes?.(root.children.map((c) => c.name));
  }, [root, onNodes, primary]);

  // материалы: свои на каждый меш, чтобы подсветка и разрез не трогали кэш GLTF
  const plane = useMemo(() => new THREE.Plane(new THREE.Vector3(0, 0, -1), 0), []);
  useEffect(() => {
    root.traverse((o) => {
      const mesh = o as THREE.Mesh;
      if (!mesh.isMesh) return;
      const p = paint(topLevelName(mesh, root));
      mesh.visible = p !== null;
      if (!p) return;
      const m = new THREE.MeshStandardMaterial({
        color: p.color,
        metalness: 0.1,
        roughness: 0.6,
        transparent: p.opacity < 1,
        opacity: p.opacity,
        side: THREE.DoubleSide,
        clippingPlanes: clip.on ? [plane] : [],
        depthWrite: p.opacity >= 0.5,
      });
      (mesh.material as THREE.Material)?.dispose?.();
      mesh.material = m;
      mesh.renderOrder = p.opacity < 1 ? 1 : 0;
    });
  }, [root, paint, clip.on, plane]);

  useEffect(() => {
    const n = new THREE.Vector3(clip.axis === "x" ? -1 : 0, clip.axis === "y" ? -1 : 0, clip.axis === "z" ? -1 : 0);
    const min = box.min[clip.axis];
    const max = box.max[clip.axis];
    const at = min + (max - min) * clip.pos;
    plane.normal.copy(n);
    plane.constant = at; // n·p + c = 0 → для n=-e: p_axis = c
  }, [clip, box, plane]);

  useEffect(() => {
    if (!controls || !primary || !view) return;
    const c = box.getCenter(new THREE.Vector3());
    // дистанция, при которой сфера габарита целиком входит в кадр по вертикали
    const d = (box.getSize(new THREE.Vector3()).length() / 2 / Math.sin(THREE.MathUtils.degToRad(camera.fov / 2))) * 1.15;
    const e = new THREE.Vector3(...EYES[view.name]).normalize().multiplyScalar(d);
    camera.up.set(0, 0, 1);
    camera.position.copy(c.clone().add(e));
    camera.near = Math.max(d / 500, 0.1);
    camera.far = d * 50;
    camera.updateProjectionMatrix();
    controls.target.copy(c);
    controls.update();
  }, [view, box, controls, camera, primary]);

  if (!primary) return <primitive object={cloned} />;
  return (
    <>
      {pins && pins.length > 0 && (
        <group>
          {pins.map((p) => (
            <mesh key={p.id} position={[p.point[0], p.point[1], p.point[2]]}>
              <sphereGeometry args={[Math.max(diag(box) / 60, 2), 16, 16]} />
              <meshStandardMaterial color={p.resolved ? "#1b7f3b" : "#f2b705"} emissive={p.resolved ? "#0a3a1a" : "#5a4200"} />
            </mesh>
          ))}
        </group>
      )}
      <primitive
        object={cloned}
        onClick={(e: { stopPropagation: () => void; object: THREE.Object3D; point: THREE.Vector3 }) => {
          e.stopPropagation();
          // мировые координаты сцены = координаты модели (мм, Z вверх): обёртка cloned уже повёрнута и отмасштабирована
          onPick?.(topLevelName(e.object, root), [e.point.x, e.point.y, e.point.z]);
        }}
        onPointerMissed={() => onPick?.(null)}
      />
      {/* сетка 50/250 мм в плоскости XY на дне габарита (Grid у drei лежит в XZ — поворачиваем) */}
      <group position={[0, 0, box.min.z - 0.5]} rotation={[Math.PI / 2, 0, 0]}>
        <Grid infiniteGrid cellSize={50} sectionSize={250} fadeDistance={6000} cellColor="#b0b7c0" sectionColor="#8a929b" />
      </group>
    </>
  );
}

export function Viewer(props: ViewerProps) {
  const { overlay, selected, dim } = props;
  const paintNow = useMemo(
    () => (overlay ? paintOverlay(overlay.changed, overlay.mix, "now") : paintSelection(selected, dim)),
    [overlay, selected, dim],
  );
  const paintWas = useMemo(() => (overlay ? paintOverlay(overlay.changed, overlay.mix, "was") : null), [overlay]);
  return (
    <ErrorBoundary onError={props.onError}>
    <Canvas
      camera={{ position: [-500, 500, 400], up: [0, 0, 1], near: 1, far: 100000, fov: 35 }}
      gl={{ preserveDrawingBuffer: true }}
      onCreated={({ gl, scene, get }) => {
        gl.localClippingEnabled = true;
        (window as unknown as { __skelcad3d?: unknown }).__skelcad3d = { gl, scene, get }; // диагностика из Playwright
      }}
      style={{ background: "transparent" }}
    >
      <hemisphereLight args={["#ffffff", "#8899aa", 0.9]} />
      <directionalLight position={[-300, 400, 600]} intensity={1.1} />
      <directionalLight position={[400, -200, 200]} intensity={0.4} />
      <Suspense fallback={null}>
        <Model
          url={props.url}
          paint={paintNow}
          clip={props.clip}
          view={props.view}
          primary
          pins={props.pins}
          onNodes={props.onNodes}
          onPick={props.onPick}
        />
        {overlay && paintWas && <Model url={overlay.baseUrl} paint={paintWas} clip={props.clip} primary={false} />}
      </Suspense>
      <OrbitControls makeDefault enableDamping={false} />
    </Canvas>
    </ErrorBoundary>
  );
}

class ErrorBoundary extends Component<{ onError?: (m: string) => void; children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  componentDidCatch(e: Error) {
    this.props.onError?.(e.message);
  }
  render() {
    return this.state.failed ? <p className="muted">{S.variant.glbFailed}</p> : this.props.children;
  }
}
