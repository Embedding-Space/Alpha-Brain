"""Crystallization service for memory clustering and analysis."""

from __future__ import annotations

import json
from typing import Any, Literal

import numpy as np
import pendulum
from sklearn.cluster import AgglomerativeClustering, DBSCAN, HDBSCAN, KMeans
from sklearn.metrics.pairwise import cosine_similarity
from structlog import get_logger

from alpha_brain.schema import Memory
from alpha_brain.crystallization_helper import get_crystallization_helper

logger = get_logger()

ClusterAlgorithm = Literal["hdbscan", "dbscan", "agglomerative", "kmeans"]


class ClusterCandidate:
    """Represents a cluster of related memories."""
    
    def __init__(self, cluster_id: int, memories: list[Memory], similarity: float, embeddings: np.ndarray | None = None):
        self.cluster_id = cluster_id
        self.memories = memories
        self.similarity = similarity
        self.memory_count = len(memories)
        self.memory_ids = [str(m.id) for m in memories]
        
        # Calculate age range for the cluster first (needed for metrics)
        created_dates = [m.created_at for m in memories]
        self.oldest = min(created_dates)
        self.newest = max(created_dates)
        
        # Calculate cluster metrics if embeddings provided
        self.centroid = None
        self.radius = None
        self.density_std = None
        self.interestingness_score = 0.0
        self.interestingness_vector = np.zeros(4)  # [size, tightness, focus, density]
        
        if embeddings is not None and len(embeddings) > 0:
            self._calculate_metrics(embeddings)
        
        # Default values - will be updated by Helper analysis
        self.title = f"Cluster {cluster_id}"
        self.summary = f"Cluster of {self.memory_count} related memories"
        self.insights: list[str] = []
        self.patterns: list[str] = []
        self.technical_knowledge: list[str] = []
        self.relationships: list[str] = []
        self.crystallizable: bool = False
        self.suggested_document_type: str = ""
        
        # Centroid memory - will be set by crystallization service
        self.centroid_memory: Memory | None = None
        self.centroid_distance: float = 0.0
    
    @property
    def time_span_days(self) -> float:
        """Get time span in days."""
        return (self.newest - self.oldest).total_seconds() / 86400.0
    
    def _calculate_metrics(self, embeddings: np.ndarray):
        """Calculate cluster metrics: centroid, radius, density."""
        # Calculate centroid (mean of all embeddings)
        self.centroid = np.mean(embeddings, axis=0)
        
        # Calculate distances from centroid
        # Using cosine distance: 1 - cosine_similarity
        centroid_norm = self.centroid / np.linalg.norm(self.centroid)
        distances = []
        
        for embedding in embeddings:
            # Normalize embedding
            emb_norm = embedding / np.linalg.norm(embedding)
            # Cosine similarity
            cos_sim = np.dot(centroid_norm, emb_norm)
            # Cosine distance
            distance = 1 - cos_sim
            distances.append(distance)
        
        distances = np.array(distances)
        
        # Radius is the maximum distance
        self.radius = float(np.max(distances))
        
        # Density standard deviation
        self.density_std = float(np.std(distances))
        
        # Calculate time span in days
        time_span_seconds = (self.newest - self.oldest).total_seconds()
        time_span_days = time_span_seconds / 86400.0  # Convert to days
        
        # Calculate interestingness vector components
        # 1. Size score: Aggressive penalty for small clusters
        optimal_size = 25.0
        if self.memory_count < 5:
            # Severe penalty for tiny clusters - exponential decay
            size_score = 0.5 * (self.memory_count / 5.0) ** 2
        elif self.memory_count < 15:
            # Linear ramp up to midpoint
            size_score = 0.5 + 4.5 * (self.memory_count - 5) / 10.0
        elif self.memory_count <= 35:
            # Peak region around 25
            # Gaussian-like peak
            deviation = abs(self.memory_count - optimal_size) / 5.0
            size_score = 10.0 * np.exp(-0.5 * deviation ** 2)
        else:
            # Gentle decline for large clusters
            size_score = 5.0 * np.exp(-((self.memory_count - 35) / 50.0))
        
        # 2. Tightness score: inverse of radius, but scaled to reasonable range
        # Map radius [0, 1] to score [10, 1]
        tightness_score = max(1.0, min(10.0, 1.0 / (self.radius + 0.1)))
        
        # 3. Temporal focus score: inverse log of time span
        # Map days [0, 365] to score [10, 1] roughly
        if time_span_days < 0.04:  # Less than 1 hour
            focus_score = 10.0
        else:
            focus_score = max(1.0, min(10.0, 2.0 / np.log10(time_span_days + 1.1)))
        
        # 4. Density uniformity score: inverse of std dev
        density_score = max(1.0, min(10.0, 1.0 / (self.density_std + 0.1)))
        
        # Store as vector
        self.interestingness_vector = np.array([
            size_score,
            tightness_score,
            focus_score,
            density_score
        ])
        
        # Calculate scalar score as weighted dot product
        # Heavily weight size to avoid tiny clusters dominating
        weights = np.array([0.5, 0.25, 0.15, 0.1])
        self.interestingness_score = float(np.dot(self.interestingness_vector, weights))


class CrystallizationService:
    """Service for analyzing memory clusters to find crystallizable knowledge."""
    
    def __init__(self, algorithm: ClusterAlgorithm = "hdbscan"):
        self.algorithm = algorithm
        self.helper = None  # Lazy initialization
        self._cached_clusters: list[ClusterCandidate] | None = None
        self._cache_params: dict[str, Any] | None = None
        self._cache_memory_ids: set[str] | None = None
        
    def cluster_memories(
        self, 
        memories: list[Memory], 
        similarity_threshold: float = 0.675,
        embedding_type: Literal["semantic", "emotional"] = "semantic",
        n_clusters: int | None = None
    ) -> list[ClusterCandidate]:
        """
        Cluster memories using the configured algorithm.
        
        Args:
            memories: List of Memory objects to cluster
            similarity_threshold: Minimum similarity for clustering (0.675 default)
            embedding_type: Which embeddings to use for clustering
            
        Returns:
            List of ClusterCandidate objects
        """
        if not memories:
            return []
        
        # Check if we can use cached results
        if self._is_cache_valid(memories, similarity_threshold, embedding_type, n_clusters):
            logger.info(
                "Using cached clustering results",
                cluster_count=len(self._cached_clusters) if self._cached_clusters else 0
            )
            return self._cached_clusters or []
            
        logger.info(
            "Starting clustering",
            memory_count=len(memories),
            algorithm=self.algorithm,
            threshold=similarity_threshold
        )
        
        # Extract embeddings as numpy array
        if embedding_type == "semantic":
            embeddings = []
            for m in memories:
                if m.semantic_embedding is not None:
                    # Handle string-encoded embeddings
                    if isinstance(m.semantic_embedding, str):
                        emb = json.loads(m.semantic_embedding)
                    else:
                        emb = m.semantic_embedding
                    embeddings.append(np.array(emb))
                else:
                    embeddings.append(np.zeros(768))
            embeddings = np.array(embeddings)
        else:
            embeddings = []
            for m in memories:
                if m.emotional_embedding is not None:
                    # Handle string-encoded embeddings
                    if isinstance(m.emotional_embedding, str):
                        emb = json.loads(m.emotional_embedding)
                    else:
                        emb = m.emotional_embedding
                    embeddings.append(np.array(emb))
                else:
                    embeddings.append(np.zeros(7))
            embeddings = np.array(embeddings)
            
        # Apply clustering algorithm
        if self.algorithm == "hdbscan":
            labels = self._cluster_hdbscan(embeddings, similarity_threshold)
        elif self.algorithm == "dbscan":
            labels = self._cluster_dbscan(embeddings, similarity_threshold)
        elif self.algorithm == "agglomerative":
            labels = self._cluster_agglomerative(embeddings, similarity_threshold)
        elif self.algorithm == "kmeans":
            if n_clusters is None:
                # This shouldn't happen if tool is used properly, but have a fallback
                import math
                n_clusters = max(2, int(math.sqrt(len(memories))))
            labels = self._cluster_kmeans(embeddings, n_clusters)
        else:
            raise ValueError(f"Unknown algorithm: {self.algorithm}")
            
        # Group memories by cluster
        clusters: dict[int, list[Memory]] = {}
        for idx, label in enumerate(labels):
            if label == -1:  # Skip noise points
                continue
            if label not in clusters:
                clusters[label] = []
            clusters[label].append(memories[idx])
            
        # Create ClusterCandidate objects
        candidates = []
        for cluster_id, cluster_memories in clusters.items():
            # Calculate average similarity within cluster
            cluster_indices = [i for i, l in enumerate(labels) if l == cluster_id]
            cluster_embeddings = embeddings[cluster_indices]
            
            if len(cluster_memories) > 1:
                similarity_matrix = cosine_similarity(cluster_embeddings)
                # Average of upper triangle (excluding diagonal)
                mask = np.triu(np.ones_like(similarity_matrix, dtype=bool), k=1)
                avg_similarity = similarity_matrix[mask].mean()
            else:
                avg_similarity = 1.0  # Single-memory cluster
                
            candidate = ClusterCandidate(
                cluster_id=cluster_id,
                memories=cluster_memories,
                similarity=avg_similarity,
                embeddings=cluster_embeddings
            )
            
            # Calculate centroid and find closest memory
            if len(cluster_memories) > 0:
                # Safety check - ensure we have valid indices
                if cluster_indices and max(cluster_indices) < len(embeddings):
                    # Note: centroid is already calculated in ClusterCandidate
                    centroid = candidate.centroid if candidate.centroid is not None else cluster_embeddings.mean(axis=0)
                    
                    # Find memory closest to centroid
                    distances = cosine_similarity([centroid], cluster_embeddings)[0]
                    closest_idx = np.argmax(distances)
                    
                    # Map back to the memory - ensure index is valid
                    if closest_idx < len(cluster_indices):
                        memory_idx = cluster_indices[closest_idx]
                        if memory_idx < len(memories):
                            candidate.centroid_memory = memories[memory_idx]
                            candidate.centroid_distance = distances[closest_idx]
            
            candidates.append(candidate)
            
        # Sort by cluster size (larger clusters first)
        candidates.sort(key=lambda c: c.memory_count, reverse=True)
        
        logger.info(
            "Clustering complete",
            total_memories=len(memories),
            clusters_found=len(candidates),
            noise_points=sum(1 for l in labels if l == -1)
        )
        
        # Cache the results
        self._cached_clusters = candidates
        self._cache_params = {
            "similarity_threshold": similarity_threshold,
            "embedding_type": embedding_type,
            "n_clusters": n_clusters,
            "algorithm": self.algorithm
        }
        self._cache_memory_ids = {str(m.id) for m in memories}
        
        return candidates
        
    def _cluster_hdbscan(self, embeddings: np.ndarray, threshold: float) -> np.ndarray:
        """HDBSCAN: Density-based clustering that finds clusters of varying densities."""
        # Convert similarity threshold to distance threshold
        # similarity = 1 - distance, so distance = 1 - similarity
        distance_threshold = 1 - threshold
        
        clusterer = HDBSCAN(
            min_cluster_size=2,  # Minimum 2 memories per cluster
            metric='cosine',
            cluster_selection_epsilon=distance_threshold,
            cluster_selection_method='eom'  # Excess of Mass
        )
        return clusterer.fit_predict(embeddings)
        
    def _cluster_dbscan(self, embeddings: np.ndarray, threshold: float) -> np.ndarray:
        """DBSCAN: Original density-based clustering algorithm."""
        distance_threshold = 1 - threshold
        
        clusterer = DBSCAN(
            eps=distance_threshold,
            min_samples=2,
            metric='cosine'
        )
        return clusterer.fit_predict(embeddings)
        
    def _cluster_agglomerative(self, embeddings: np.ndarray, threshold: float) -> np.ndarray:
        """Agglomerative: Hierarchical clustering that merges similar clusters."""
        distance_threshold = 1 - threshold
        
        clusterer = AgglomerativeClustering(
            n_clusters=None,
            distance_threshold=distance_threshold,
            metric='cosine',
            linkage='average'
        )
        return clusterer.fit_predict(embeddings)
        
    def _cluster_kmeans(self, embeddings: np.ndarray, n_clusters: int) -> np.ndarray:
        """K-Means: Classic clustering that partitions into K clusters."""
        # K-means doesn't use similarity threshold, needs number of clusters
        n_clusters = max(2, min(n_clusters, len(embeddings) // 2))
        
        clusterer = KMeans(
            n_clusters=n_clusters,
            random_state=42,
            n_init=10
        )
        return clusterer.fit_predict(embeddings)
    
    async def analyze_clusters_with_helper(
        self,
        candidates: list[ClusterCandidate],
        limit: int = 10
    ) -> list[ClusterCandidate]:
        """
        Analyze cluster candidates using Helper to extract insights.
        
        Args:
            candidates: List of ClusterCandidate objects to analyze
            limit: Maximum number of clusters to analyze
            
        Returns:
            Updated list of ClusterCandidate objects with Helper analysis
        """
        # Lazy initialization of helper
        if self.helper is None:
            self.helper = get_crystallization_helper()
            
        analyzed_candidates = []
        
        for i, candidate in enumerate(candidates[:limit]):
            try:
                logger.info(
                    "analyzing_cluster_with_helper",
                    cluster_id=candidate.cluster_id,
                    memory_count=candidate.memory_count,
                    index=i+1,
                    total=min(len(candidates), limit)
                )
                
                # Analyze the cluster with Helper
                analysis = await self.helper.analyze_cluster(
                    memories=candidate.memories,
                    similarity_score=candidate.similarity
                )
                
                # Update candidate with analysis results
                candidate.title = analysis.title
                candidate.summary = analysis.summary
                candidate.insights = analysis.insights
                candidate.patterns = analysis.patterns
                candidate.technical_knowledge = analysis.technical_knowledge
                candidate.relationships = analysis.relationships
                candidate.crystallizable = analysis.crystallizable
                candidate.suggested_document_type = analysis.suggested_document_type
                
                analyzed_candidates.append(candidate)
                
            except Exception as e:
                logger.error(
                    "cluster_analysis_failed",
                    cluster_id=candidate.cluster_id,
                    error=str(e)
                )
                # Keep the candidate with default values
                analyzed_candidates.append(candidate)
                
        return analyzed_candidates
    
    def _is_cache_valid(
        self,
        memories: list[Memory],
        similarity_threshold: float,
        embedding_type: Literal["semantic", "emotional"],
        n_clusters: int | None
    ) -> bool:
        """Check if cached clusters are valid for the given parameters."""
        if self._cached_clusters is None or self._cache_params is None:
            return False
        
        # Check if parameters match
        params_match = (
            self._cache_params.get("similarity_threshold") == similarity_threshold and
            self._cache_params.get("embedding_type") == embedding_type and
            self._cache_params.get("n_clusters") == n_clusters and
            self._cache_params.get("algorithm") == self.algorithm
        )
        
        if not params_match:
            return False
        
        # Check if the same memories are being clustered
        current_memory_ids = {str(m.id) for m in memories}
        return current_memory_ids == self._cache_memory_ids
    
    def get_cached_clusters(self) -> list[ClusterCandidate] | None:
        """Get cached clusters if available."""
        return self._cached_clusters
    
    def clear_cache(self):
        """Clear the cluster cache."""
        self._cached_clusters = None
        self._cache_params = None
        self._cache_memory_ids = None


# Global instance
_crystallization_service = None


def get_crystallization_service(algorithm: ClusterAlgorithm = "hdbscan") -> CrystallizationService:
    """Get the crystallization service instance."""
    global _crystallization_service
    if _crystallization_service is None or _crystallization_service.algorithm != algorithm:
        _crystallization_service = CrystallizationService(algorithm)
    return _crystallization_service