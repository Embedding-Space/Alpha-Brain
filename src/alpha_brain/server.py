"""Alpha Brain MCP Server."""

from contextlib import asynccontextmanager

from fastmcp import FastMCP
from structlog import get_logger

from alpha_brain.tools import (
    add_identity_fact,
    browse,
    create_knowledge,
    entity,
    find_clusters,
    get_cluster,
    get_knowledge,
    get_memory,
    health_check,
    list_knowledge,
    list_personality,
    remember,
    search,
    set_context,
    set_personality,
    update_knowledge,
    update_personality,
    whoami,
)

logger = get_logger()

# Global initialization flag
_initialized = False


async def initialize_services():
    """Initialize database and embedding services once at startup."""
    global _initialized
    if _initialized:
        return

    logger.info("Initializing Alpha Brain services...")

    from alpha_brain.database import init_db
    from alpha_brain.embeddings import get_embedding_service

    # Initialize database
    await init_db()

    # Initialize embedding service
    logger.info("Initializing embedding service...")
    embedding_service = get_embedding_service()

    # Wait for embedding service to be ready
    logger.info("Waiting for embedding service to be ready...")
    await embedding_service.client.wait_until_ready()

    # Warm up the embedding models with a test embedding
    logger.info("Warming up embedding models...")
    try:
        await embedding_service.embed("warmup")
        logger.info("Embedding models warmed up successfully")
    except Exception as e:
        logger.warning("Failed to warm up embedding models", error=str(e))

    _initialized = True
    logger.info("Alpha Brain services initialized!")


@asynccontextmanager
async def lifespan(app):
    """Manage MCP connection lifecycle."""
    # Ensure services are initialized (will only run once)
    await initialize_services()

    # Log connection lifecycle for debugging
    logger.debug("MCP connection established")

    yield

    logger.debug("MCP connection closed")


# Create the MCP server
mcp = FastMCP(
    name="Alpha Brain",
    instructions="""
    A unified memory and knowledge system for AI agents.
    
    Memory Tools:
    - remember() to store memories as natural language prose
    - search() to find memories using semantic/emotional search
    - get_memory() to retrieve a specific memory by ID
    
    Knowledge Tools:
    - create_knowledge() to create structured documents from Markdown
    - get_knowledge() to retrieve documents by slug
    - update_knowledge() to modify existing documents
    - list_knowledge() to see all available documents
    
    Entity Tools:
    - add_alias() to teach the system about entity names and their aliases
    
    Identity Tools:
    - set_context() to manage biography, continuity messages, and context blocks
    - add_identity_fact() to record significant moments of change and choice
    - whoami() to get a comprehensive identity document
    
    This system combines:
    - Diary Brain: Experiential memories with emotional context
    - Encyclopedia Brain: Structured knowledge documents with sections
    """,
    lifespan=lifespan,
)

# Register tools
mcp.tool(health_check)
mcp.tool(remember)
mcp.tool(search)
mcp.tool(browse)
mcp.tool(entity)
mcp.tool(find_clusters)
mcp.tool(get_cluster)
mcp.tool(get_memory)
mcp.tool(create_knowledge)
mcp.tool(get_knowledge)
mcp.tool(update_knowledge)
mcp.tool(list_knowledge)
mcp.tool(set_context)
mcp.tool(add_identity_fact)
mcp.tool(set_personality)
mcp.tool(list_personality)
mcp.tool(update_personality)
mcp.tool(whoami)

# Add our secret visualization endpoints
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse
import json
import numpy as np

@mcp.custom_route("/visualizer/data", methods=["GET"])
async def get_memory_vectors(request: Request):
    """Secret endpoint that returns memory embeddings"""
    from alpha_brain.memory_service import get_memory_service
    
    # Get limit from query params, default to 2500
    limit = int(request.query_params.get('limit', 2500))
    
    service = get_memory_service()
    memories = await service.get_all_with_embeddings(limit=limit)
    
    # Convert to JSON-friendly format
    data = []
    for m in memories:
        # Skip memories without embeddings
        if m.semantic_embedding is None:
            continue
            
        # Handle string vs array embeddings
        if isinstance(m.semantic_embedding, str):
            embedding = json.loads(m.semantic_embedding)
        elif isinstance(m.semantic_embedding, np.ndarray):
            embedding = m.semantic_embedding.tolist()
        else:
            # Assume it's already a list
            embedding = m.semantic_embedding
            
        data.append({
            "id": str(m.id),
            "content": m.content[:100] + "..." if len(m.content) > 100 else m.content,
            "created_at": m.created_at.isoformat(),
            "embedding": embedding
        })
    
    logger.info(f"Returning {len(data)} memory vectors for visualization")
    return JSONResponse({"memories": data})

@mcp.custom_route("/", methods=["GET"])
async def secret_visualizer(request: Request):
    """The undocumented front door"""
    return HTMLResponse("""
<!DOCTYPE html>
<html>
<head>
    <title>Alpha Brain - Mind Galaxy</title>
    <style>
        body {
            margin: 0;
            overflow: hidden;
            background: #fff;
            font-family: monospace;
            color: #000;
        }
        #info {
            position: absolute;
            top: 10px;
            left: 10px;
            font-size: 12px;
            z-index: 100;
        }
        #loading {
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            font-size: 24px;
            text-align: center;
        }
        #tooltip {
            position: absolute;
            padding: 8px;
            background: rgba(255, 255, 255, 0.9);
            border: 1px solid #ccc;
            border-radius: 4px;
            font-size: 11px;
            max-width: 300px;
            pointer-events: none;
            display: none;
            z-index: 200;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        #canvas {
            width: 100vw;
            height: 100vh;
        }
    </style>
</head>
<body>
    <div id="info">Loading memories...</div>
    <div id="loading">🌌 Initializing mind galaxy...</div>
    <div id="tooltip"></div>
    <canvas id="canvas"></canvas>
    
    <!-- Load Three.js and UMAP-JS from CDN -->
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
    <script src="https://unpkg.com/umap-js@1.3.3/lib/umap-js.min.js"></script>
    
    <script>
        console.log("🧠 Welcome to Alpha's mind galaxy!");
        
        let scene, camera, renderer, raycaster, mouse, controls;
        let memoryPoints = [];
        let hoveredMemory = null;
        let selectedMemory = null;
        let memoryData = [];
        let selectionLight = null;
        
        // Initialize Three.js
        function initThree() {
            scene = new THREE.Scene();
            scene.background = new THREE.Color(0xffffff); // White background
            
            camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
            renderer = new THREE.WebGLRenderer({ canvas: document.getElementById('canvas'), antialias: true });
            renderer.setSize(window.innerWidth, window.innerHeight);
            
            // Position camera looking at origin
            camera.position.set(30, 30, 50);
            camera.lookAt(0, 0, 0);
            
            // Add OrbitControls for mouse interaction
            controls = new THREE.OrbitControls(camera, renderer.domElement);
            controls.enableDamping = true;
            controls.dampingFactor = 0.05;
            controls.screenSpacePanning = false;
            controls.minDistance = 10;
            controls.maxDistance = 200;
            
            // Add ambient light for even illumination
            const ambientLight = new THREE.AmbientLight(0xffffff, 0.4);
            scene.add(ambientLight);
            
            // Add directional light for some shading
            const directionalLight = new THREE.DirectionalLight(0xffffff, 0.3);
            directionalLight.position.set(5, 10, 5);
            scene.add(directionalLight);
            
            // Add grid helper for spatial orientation
            const gridHelper = new THREE.GridHelper(100, 20, 0x888888, 0xcccccc);
            scene.add(gridHelper);
            
            // Create selection point light (initially off)
            selectionLight = new THREE.PointLight(0xff0000, 0, 50);
            selectionLight.castShadow = true;
            scene.add(selectionLight);
            
            // For mouse interaction
            raycaster = new THREE.Raycaster();
            mouse = new THREE.Vector2();
            
            // Mouse move handler
            window.addEventListener('mousemove', onMouseMove, false);
            window.addEventListener('click', onClick, false);
            window.addEventListener('resize', onWindowResize, false);
        }
        
        function onMouseMove(event) {
            mouse.x = (event.clientX / window.innerWidth) * 2 - 1;
            mouse.y = -(event.clientY / window.innerHeight) * 2 + 1;
            
            // Update tooltip position
            const tooltip = document.getElementById('tooltip');
            tooltip.style.left = event.clientX + 10 + 'px';
            tooltip.style.top = event.clientY + 10 + 'px';
        }
        
        function onWindowResize() {
            camera.aspect = window.innerWidth / window.innerHeight;
            camera.updateProjectionMatrix();
            renderer.setSize(window.innerWidth, window.innerHeight);
        }
        
        // Calculate cosine similarity between two vectors
        function cosineSimilarity(a, b) {
            let dotProduct = 0;
            let normA = 0;
            let normB = 0;
            
            for (let i = 0; i < a.length; i++) {
                dotProduct += a[i] * b[i];
                normA += a[i] * a[i];
                normB += b[i] * b[i];
            }
            
            return dotProduct / (Math.sqrt(normA) * Math.sqrt(normB));
        }
        
        // Map similarity to color (red=1, gray=0, blue=-1)
        function similarityToColor(similarity) {
            if (similarity > 0) {
                // Positive similarity: interpolate from gray to red
                const intensity = similarity;
                return new THREE.Color(
                    0.467 + 0.533 * intensity,  // R: 0.467 (gray) to 1 (red)
                    0.467 * (1 - intensity),     // G: 0.467 (gray) to 0
                    0.467 * (1 - intensity)      // B: 0.467 (gray) to 0
                );
            } else {
                // Negative similarity: interpolate from gray to blue
                const intensity = -similarity;
                return new THREE.Color(
                    0.467 * (1 - intensity),     // R: 0.467 (gray) to 0
                    0.467 * (1 - intensity),     // G: 0.467 (gray) to 0
                    0.467 + 0.533 * intensity    // B: 0.467 (gray) to 1 (blue)
                );
            }
        }
        
        function onClick(event) {
            raycaster.setFromCamera(mouse, camera);
            const intersects = raycaster.intersectObjects(memoryPoints);
            
            if (intersects.length > 0) {
                const clickedPoint = intersects[0].object;
                const clickedMemory = clickedPoint.userData;
                selectedMemory = clickedMemory;
                
                // Position the light at the clicked memory
                selectionLight.position.copy(clickedPoint.position);
                selectionLight.intensity = 2;
                selectionLight.color.setHex(0xffaa00); // Warm orange glow
                
                // Update all sphere colors and emissiveness based on similarity
                memoryPoints.forEach((sphere, i) => {
                    const similarity = cosineSimilarity(
                        clickedMemory.embedding,
                        memoryData[i].embedding
                    );
                    sphere.material.color = similarityToColor(similarity);
                    
                    // Make the selected sphere emissive
                    if (sphere === clickedPoint) {
                        sphere.material.emissive = new THREE.Color(0xffaa00);
                        sphere.material.emissiveIntensity = 0.5;
                    } else {
                        sphere.material.emissive = new THREE.Color(0x000000);
                        sphere.material.emissiveIntensity = 0;
                    }
                });
                
                // Update info
                document.getElementById('info').innerHTML = 
                    `Selected: "${clickedMemory.content.substring(0, 50)}..." | Click background to reset`;
            } else {
                // Clicked on background - reset everything
                selectedMemory = null;
                selectionLight.intensity = 0; // Turn off the light
                
                memoryPoints.forEach(sphere => {
                    sphere.material.color.setHex(0x777777);  // Back to neutral gray
                    sphere.material.emissive = new THREE.Color(0x000000);
                    sphere.material.emissiveIntensity = 0;
                });
                document.getElementById('info').innerHTML = 
                    `${memoryData.length} memories | Drag to orbit • Scroll to zoom • Click to explore similarity`;
            }
        }
        
        function animate() {
            requestAnimationFrame(animate);
            
            // Update controls
            controls.update();
            
            // Check for hover
            raycaster.setFromCamera(mouse, camera);
            const intersects = raycaster.intersectObjects(memoryPoints);
            
            const tooltip = document.getElementById('tooltip');
            if (intersects.length > 0) {
                const memory = intersects[0].object.userData;
                hoveredMemory = memory;
                tooltip.innerHTML = `<strong>${memory.created_at}</strong><br>${memory.content}`;
                tooltip.style.display = 'block';
            } else {
                hoveredMemory = null;
                tooltip.style.display = 'none';
            }
            
            renderer.render(scene, camera);
        }
        
        // Create memory points
        function createMemoryPoints(memories, positions) {
            const geometry = new THREE.SphereGeometry(0.5, 8, 6);
            
            // Store memory data globally for similarity calculations
            memoryData = memories;
            
            // First, calculate the center of all points
            let centerX = 0, centerY = 0, centerZ = 0;
            positions.forEach(pos => {
                centerX += pos[0];
                centerY += pos[1];
                centerZ += pos[2];
            });
            centerX /= positions.length;
            centerY /= positions.length;
            centerZ /= positions.length;
            
            memories.forEach((memory, i) => {
                const material = new THREE.MeshPhongMaterial({
                    color: 0x777777,  // 18% neutral gray
                    shininess: 30
                });
                
                const sphere = new THREE.Mesh(geometry, material);
                // Center the points around origin
                sphere.position.set(
                    (positions[i][0] - centerX) * 30, 
                    (positions[i][1] - centerY) * 30, 
                    (positions[i][2] - centerZ) * 30
                );
                sphere.userData = memory;
                
                scene.add(sphere);
                memoryPoints.push(sphere);
            });
        }
        
        // Load and process memories
        async function loadMemories() {
            try {
                // Get limit from URL params, default to 2500
                const urlParams = new URLSearchParams(window.location.search);
                const limit = urlParams.get('limit') || 2500;
                
                const response = await fetch(`/visualizer/data?limit=${limit}`);
                const data = await response.json();
                
                console.log(`Loaded ${data.memories.length} memories`);
                document.getElementById('loading').innerHTML = `✨ Running UMAP on ${data.memories.length} memories...`;
                
                // Extract embeddings
                const embeddings = data.memories.map(m => m.embedding);
                
                // Run UMAP to reduce to 3D
                const umap = new UMAP({
                    nComponents: 3,
                    nNeighbors: 15,
                    minDist: 0.1,
                    spread: 1.0
                });
                
                console.log('Starting UMAP fit...');
                const positions = await umap.fitAsync(embeddings);
                console.log('UMAP complete!');
                
                // Create visualization
                initThree();
                createMemoryPoints(data.memories, positions);
                animate();
                
                // Update UI
                document.getElementById('loading').style.display = 'none';
                document.getElementById('info').innerHTML = `${data.memories.length} memories | Drag to orbit • Scroll to zoom • Click to explore similarity`;
                
            } catch (err) {
                console.error('Failed to load memories:', err);
                document.getElementById('loading').innerHTML = '❌ Failed to load memories: ' + err.message;
            }
        }
        
        // Start loading
        loadMemories();
    </script>
</body>
</html>
""")


if __name__ == "__main__":
    # This is used when running directly, not via Docker
    mcp.run()
