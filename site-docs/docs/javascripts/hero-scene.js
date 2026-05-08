/**
 * Flowing Wave Field — abstract background animation using Three.js.
 *
 * A grid of particles undulates using layered sine waves, creating an
 * organic, ocean-like surface. Particles are orange (#F97316), connections
 * are white with low opacity. Mouse movement warps the wave locally.
 */

;(function () {
    let animationId = null;
    let renderer = null;
    let mouseMoveHandler = null;
    let resizeHandler = null;

    function teardown() {
        if (animationId) { cancelAnimationFrame(animationId); animationId = null; }
        if (renderer) { renderer.dispose(); renderer = null; }
        if (mouseMoveHandler) { document.removeEventListener('mousemove', mouseMoveHandler); mouseMoveHandler = null; }
        if (resizeHandler) { window.removeEventListener('resize', resizeHandler); resizeHandler = null; }
    }

    function init() {
        teardown();
        const canvas = document.getElementById('hero-canvas');
        if (!canvas) return;

        const scene = new THREE.Scene();
        renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true });
        renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

        const camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 1, 1000);
        camera.position.set(0, 120, 200);
        camera.lookAt(0, 0, 0);

        const COLS = 50, ROWS = 50, SPACING = 8;
        const PARTICLE_COUNT = COLS * ROWS;
        const offsetX = ((COLS - 1) * SPACING) / 2;
        const offsetZ = ((ROWS - 1) * SPACING) / 2;

        const geometry = new THREE.BufferGeometry();
        const positions = new Float32Array(PARTICLE_COUNT * 3);
        for (let row = 0; row < ROWS; row++) {
            for (let col = 0; col < COLS; col++) {
                const i = (row * COLS + col) * 3;
                positions[i]     = col * SPACING - offsetX;
                positions[i + 1] = 0;
                positions[i + 2] = row * SPACING - offsetZ;
            }
        }
        geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));

        function createCircleTexture() {
            const c = document.createElement('canvas');
            c.width = 32; c.height = 32;
            const ctx = c.getContext('2d');
            const grad = ctx.createRadialGradient(16, 16, 0, 16, 16, 16);
            grad.addColorStop(0,   'rgba(255,255,255,1)');
            grad.addColorStop(0.4, 'rgba(255,255,255,0.8)');
            grad.addColorStop(1,   'rgba(255,255,255,0)');
            ctx.fillStyle = grad;
            ctx.fillRect(0, 0, 32, 32);
            const tex = new THREE.Texture(c);
            tex.needsUpdate = true;
            return tex;
        }

        const points = new THREE.Points(geometry, new THREE.PointsMaterial({
            color: 0xF97316, size: 2.5,
            map: createCircleTexture(),
            transparent: true, alphaTest: 0.01, opacity: 0.9,
            depthWrite: false, blending: THREE.AdditiveBlending
        }));
        scene.add(points);

        const maxLines = (COLS - 1) * ROWS + COLS * (ROWS - 1);
        const linePositions = new Float32Array(maxLines * 6);
        const lineGeometry = new THREE.BufferGeometry();
        lineGeometry.setAttribute('position',
            new THREE.BufferAttribute(linePositions, 3).setUsage(THREE.DynamicDrawUsage));
        const lines = new THREE.LineSegments(lineGeometry,
            new THREE.LineBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.08, depthWrite: false }));
        scene.add(lines);

        const mouse = { x: 9999, y: 9999 };
        mouseMoveHandler = (e) => {
            const rect = canvas.parentNode.getBoundingClientRect();
            mouse.x =  ((e.clientX - rect.left) / rect.width)  * 2 - 1;
            mouse.y = -((e.clientY - rect.top)  / rect.height) * 2 + 1;
        };
        document.addEventListener('mousemove', mouseMoveHandler);

        resizeHandler = () => {
            const container = canvas.parentNode;
            if (!container) return;
            renderer.setSize(container.clientWidth, container.clientHeight);
            camera.aspect = container.clientWidth / container.clientHeight;
            camera.updateProjectionMatrix();
        };
        window.addEventListener('resize', resizeHandler);
        resizeHandler();

        const clock = new THREE.Clock();
        function animate() {
            animationId = requestAnimationFrame(animate);
            const t = clock.getElapsedTime();
            const pos = points.geometry.attributes.position.array;

            const mouseVec = new THREE.Vector3(mouse.x, mouse.y, 0.5);
            mouseVec.unproject(camera);
            const dir = mouseVec.sub(camera.position).normalize();
            const dist = -camera.position.y / dir.y;
            const mouseWorld = camera.position.clone().add(dir.multiplyScalar(dist));

            for (let row = 0; row < ROWS; row++) {
                for (let col = 0; col < COLS; col++) {
                    const i = (row * COLS + col) * 3;
                    const x = pos[i], z = pos[i + 2];
                    let y = Math.sin(x * 0.04 + t * 0.8) * 12
                          + Math.sin(z * 0.06 + t * 1.2) * 8
                          + Math.sin((x + z) * 0.05 + t * 0.6) * 5;
                    const dx = x - mouseWorld.x, dz = z - mouseWorld.z;
                    const mouseDist = Math.sqrt(dx * dx + dz * dz);
                    if (mouseDist < 60) y += (1 - mouseDist / 60) * 20;
                    pos[i + 1] = y;
                }
            }
            points.geometry.attributes.position.needsUpdate = true;

            const lnPos = lines.geometry.attributes.position.array;
            let li = 0;
            for (let row = 0; row < ROWS; row++) {
                for (let col = 0; col < COLS; col++) {
                    const i = (row * COLS + col) * 3;
                    if (col < COLS - 1) {
                        const j = (row * COLS + col + 1) * 3;
                        lnPos[li++]=pos[i];   lnPos[li++]=pos[i+1]; lnPos[li++]=pos[i+2];
                        lnPos[li++]=pos[j];   lnPos[li++]=pos[j+1]; lnPos[li++]=pos[j+2];
                    }
                    if (row < ROWS - 1) {
                        const j = ((row + 1) * COLS + col) * 3;
                        lnPos[li++]=pos[i];   lnPos[li++]=pos[i+1]; lnPos[li++]=pos[i+2];
                        lnPos[li++]=pos[j];   lnPos[li++]=pos[j+1]; lnPos[li++]=pos[j+2];
                    }
                }
            }
            lines.geometry.attributes.position.needsUpdate = true;
            lines.geometry.setDrawRange(0, li / 3);

            scene.rotation.y += 0.0008;
            renderer.render(scene, camera);
        }
        animate();
    }

    function safeInit() {
        if (typeof THREE === 'undefined') return;
        init();
    }

    if (typeof document$ !== 'undefined') { document$.subscribe(safeInit); }
    if (document.readyState === 'loading') { document.addEventListener('DOMContentLoaded', safeInit); }
    else { safeInit(); }
})();
