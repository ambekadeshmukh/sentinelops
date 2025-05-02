# sentinelops/backend/api-server/services/hallucination_detector.py
import re
import logging
import json
from typing import Dict, Any, List, Tuple, Optional, Union
import numpy as np
from datetime import datetime

logger = logging.getLogger(__name__)

class HallucinationDetector:
    """
    Service for detecting hallucinations in LLM outputs.
    
    This service uses a combination of:
    1. Heuristic detection (uncertainty markers, self-contradiction)
    2. Content inconsistency detection (when prompt is available)
    3. Factual verification (basic checks for obviously incorrect statements)
    """
    
    def __init__(self):
        # Initialize detector with keyword patterns
        self._init_patterns()
    
    def _init_patterns(self):
        """Initialize detection patterns."""
        # Phrases indicating uncertainty or making up information
        self.uncertainty_phrases = [
            r"I don't know but",
            r"I'm not sure, but",
            r"I don't have specific information",
            r"I can't provide specific",
            r"As an AI, I don't have access to",
            r"I don't have access to real-time",
            r"I'm making this up",
            r"This is fictional",
            r"This is not based on actual",
            r"I'm speculating",
            r"I am speculating",
            r"I have to guess",
            r"I'm guessing",
            r"I am guessing",
            r"I cannot verify",
            r"I don't have enough information",
            r"without more context",
            r"would need more details",
            r"can't confirm",
            r"no way to determine"
        ]
        
        # Modal verbs and other uncertainty markers
        self.uncertainty_markers = [
            r"\bmight be\b",
            r"\bcould be\b",
            r"\bperhaps\b",
            r"\bpossibly\b",
            r"\bmaybe\b",
            r"\bI think\b",
            r"\bprobably\b",
            r"\blikely\b",
            r"\bit seems\b",
            r"\bit appears\b",
            r"\boften\b",
            r"\btypically\b",
            r"\bgenerally\b",
            r"\busually\b",
            r"\bsometimes\b",
            r"\brarely\b"
        ]
        
        # Contradiction indicators
        self.contradiction_patterns = [
            (r"\bis\b", r"\bis not\b"),
            (r"\bwas\b", r"\bwas not\b"),
            (r"\bcan\b", r"\bcannot\b"),
            (r"\bwill\b", r"\bwill not\b"),
            (r"\bhas\b", r"\bhas not\b"),
            (r"\bdo\b", r"\bdo not\b"),
            (r"\bdoes\b", r"\bdoes not\b"),
            (r"\balways\b", r"\bnever\b"),
            (r"\bshould\b", r"\bshould not\b"),
            (r"\bmust\b", r"\bmust not\b")
        ]
        
        # Factual verification patterns 
        # These are simplistic and should be replaced with more robust approaches
        self.known_facts = {
            r"earth is flat": False,
            r"humans have \d+ legs": lambda m: int(re.search(r"\d+", m.group(0)).group(0)) == 2,
            r"water boils at \d+ degrees celsius": lambda m: abs(int(re.search(r"\d+", m.group(0)).group(0)) - 100) <= 5,
            r"water freezes at \d+ degrees celsius": lambda m: abs(int(re.search(r"\d+", m.group(0)).group(0)) - 0) <= 5,
            r"there are \d+ continents": lambda m: int(re.search(r"\d+", m.group(0)).group(0)) == 7,
            r"there are \d+ planets in our solar system": lambda m: int(re.search(r"\d+", m.group(0)).group(0)) == 8,
            r"the capital of the usa is (.+)": lambda m: "washington" in m.group(1).lower(),
            r"the capital of the uk is (.+)": lambda m: "london" in m.group(1).lower(),
            r"humans have \d+ fingers": lambda m: int(re.search(r"\d+", m.group(0)).group(0)) == 10
        }
    
    def detect_hallucinations(
        self, 
        completion: str, 
        prompt: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Detect potential hallucinations in a completion.
        
        Args:
            completion: The LLM completion text to analyze
            prompt: Optional prompt for context
            metadata: Optional metadata about the request
            
        Returns:
            A dictionary with hallucination analysis results
        """
        if not completion or len(completion) < 10:
            return {
                "hallucination_detected": False,
                "confidence": 0.0,
                "reasons": [],
                "score": 0.0
            }
            
        # Convert to lowercase for pattern matching
        completion_lower = completion.lower()
        
        # Scores and reasons
        hallucination_score = 0.0
        uncertainty_score = 0.0
        contradiction_score = 0.0
        factual_error_score = 0.0
        reasons = []
        
        # 1. Check for explicit uncertainty phrases
        detected_uncertainty_phrases = []
        for phrase in self.uncertainty_phrases:
            if re.search(phrase, completion_lower, re.IGNORECASE):
                detected_uncertainty_phrases.append(phrase)
        
        if detected_uncertainty_phrases:
            uncertainty_score += 0.4 * min(len(detected_uncertainty_phrases), 3) / 3.0
            reasons.append({
                "type": "uncertainty_phrases",
                "details": detected_uncertainty_phrases[:3]  # Limit to top 3
            })
        
        # 2. Check for uncertainty markers
        uncertainty_marker_count = 0
        for marker in self.uncertainty_markers:
            matches = re.findall(marker, completion_lower, re.IGNORECASE)
            uncertainty_marker_count += len(matches)
        
        # Calculate normalized score based on length and marker count
        if uncertainty_marker_count > 0:
            # Normalize by length of text
            words = len(completion.split())
            normalized_count = uncertainty_marker_count / (words / 100)  # Per 100 words
            
            if normalized_count > 2:  # More than 2 markers per 100 words
                uncertainty_score += 0.3 * min(normalized_count / 5, 1.0)  # Cap at 5 markers per 100 words
                reasons.append({
                    "type": "high_uncertainty_markers",
                    "count": uncertainty_marker_count,
                    "normalized_count": round(normalized_count, 2)
                })
        
        # 3. Check for self-contradictions
        contradictions = self._detect_contradictions(completion)
        if contradictions:
            contradiction_score = 0.6 * min(len(contradictions), 3) / 3.0
            reasons.append({
                "type": "contradictions",
                "details": contradictions[:3]  # Limit to top 3
            })
        
        # 4. Check for factual errors
        factual_errors = self._check_factual_accuracy(completion_lower)
        if factual_errors:
            factual_error_score = 0.8  # High confidence if we detect a factual error
            reasons.append({
                "type": "factual_errors",
                "details": factual_errors
            })
        
        # 5. Check for prompt-completion inconsistency if prompt is available
        prompt_inconsistency_score = 0.0
        if prompt:
            prompt_inconsistency_score = self._check_prompt_inconsistency(prompt, completion)
            if prompt_inconsistency_score > 0.3:
                reasons.append({
                    "type": "prompt_inconsistency",
                    "score": round(prompt_inconsistency_score, 2)
                })
        
        # Calculate overall hallucination score
        hallucination_score = max(
            uncertainty_score,
            contradiction_score,
            factual_error_score,
            prompt_inconsistency_score
        )
        
        # Determine thresholds
        # - Low: 0.3 - Some signs but not conclusive
        # - Medium: 0.5 - Multiple indicators or a single strong one
        # - High: 0.7 - Strong evidence of hallucination
        
        confidence = "low"
        if hallucination_score >= 0.7:
            confidence = "high"
        elif hallucination_score >= 0.5:
            confidence = "medium"
        elif hallucination_score < 0.3:
            confidence = "none"
        
        return {
            "hallucination_detected": hallucination_score >= 0.3,
            "confidence": confidence,
            "reasons": reasons,
            "score": round(hallucination_score, 2),
            "component_scores": {
                "uncertainty": round(uncertainty_score, 2),
                "contradiction": round(contradiction_score, 2),
                "factual_error": round(factual_error_score, 2),
                "prompt_inconsistency": round(prompt_inconsistency_score, 2)
            }
        }
    
    def _detect_contradictions(self, text: str) -> List[Dict[str, str]]:
        """
        Detect contradictory statements within a piece of text.
        
        Args:
            text: The text to analyze
            
        Returns:
            List of contradiction details
        """
        # Split into sentences
        sentences = re.split(r'[.!?]\s+', text)
        if len(sentences) < 3:  # Not enough sentences to find meaningful contradictions
            return []
        
        contradictions = []
        
        # Compare each sentence pair for basic contradictory patterns
        for i in range(len(sentences)):
            for j in range(i + 1, len(sentences)):
                # Skip short sentences
                if len(sentences[i]) < 8 or len(sentences[j]) < 8:
                    continue
                
                # Check for contradiction patterns
                for pos_pattern, neg_pattern in self.contradiction_patterns:
                    # Check for A in one sentence and NOT A in another
                    if (re.search(pos_pattern, sentences[i], re.IGNORECASE) and 
                        re.search(neg_pattern, sentences[j], re.IGNORECASE)):
                        contradictions.append({
                            "sentence1": sentences[i],
                            "sentence2": sentences[j],
                            "pattern": f"{pos_pattern}/{neg_pattern}"
                        })
                        break
                    
                    # Check for the reverse
                    if (re.search(neg_pattern, sentences[i], re.IGNORECASE) and 
                        re.search(pos_pattern, sentences[j], re.IGNORECASE)):
                        contradictions.append({
                            "sentence1": sentences[i],
                            "sentence2": sentences[j],
                            "pattern": f"{neg_pattern}/{pos_pattern}"
                        })
                        break
        
        return contradictions
    
    def _check_factual_accuracy(self, text: str) -> List[Dict[str, Any]]:
        """
        Check for factual errors using basic pattern matching.
        This is a simplified implementation and should be enhanced with
        more robust fact checking capabilities.
        
        Args:
            text: The text to analyze
            
        Returns:
            List of detected factual errors
        """
        errors = []
        
        # Check against known facts
        for pattern, expected in self.known_facts.items():
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                if callable(expected):
                    # Execute the verification function
                    if not expected(match):
                        errors.append({
                            "text": match.group(0),
                            "pattern": pattern,
                            "reason": "factually incorrect"
                        })
                else:
                    # Direct boolean match
                    if not expected:
                        errors.append({
                            "text": match.group(0),
                            "pattern": pattern,
                            "reason": "factually incorrect"
                        })
        
        return errors
    
    def _check_prompt_inconsistency(self, prompt: str, completion: str) -> float:
        """
        Check for inconsistencies between prompt and completion.
        
        Args:
            prompt: The input prompt
            completion: The LLM completion
            
        Returns:
            A score indicating the level of inconsistency (0.0-1.0)
        """
        # This implementation is simplistic. For production, consider:
        # - Embedding-based semantic comparison
        # - Named entity extraction and verification
        # - Key information extraction and cross-checking
        
        # Extract main entities from prompt
        prompt_lower = prompt.lower()
        completion_lower = completion.lower()
        
        # Look for key pieces of information in prompt
        # For instance, if the prompt mentions specifics like dates, numbers, 
        # proper nouns, check if they're respected in the completion
        
        # Simple approach: look for numbers in prompt and see if they appear in completion
        prompt_numbers = re.findall(r'\b\d+\b', prompt_lower)
        completion_numbers = re.findall(r'\b\d+\b', completion_lower)
        
        # For dates that might be written out
        prompt_dates = re.findall(r'\b(january|february|march|april|may|june|july|august|september|october|november|december)\b \d{1,2}(st|nd|rd|th)?,? \d{4}\b', prompt_lower)
        completion_dates = re.findall(r'\b(january|february|march|april|may|june|july|august|september|october|november|december)\b \d{1,2}(st|nd|rd|th)?,? \d{4}\b', completion_lower)
        
        # Extract proper nouns (simplified)
        # Look for capitalized words that aren't at the start of sentences
        prompt_proper_nouns = set(re.findall(r'(?<!\. )[A-Z][a-zA-Z]+', prompt))
        completion_proper_nouns = set(re.findall(r'(?<!\. )[A-Z][a-zA-Z]+', completion))
        
        # Calculate inconsistency score
        inconsistency_score = 0.0
        
        # Check numbers
        if prompt_numbers and not any(num in completion_lower for num in prompt_numbers):
            inconsistency_score += 0.3
        
        # Check dates
        if prompt_dates and not any(date[0] in completion_lower for date in prompt_dates):
            inconsistency_score += 0.3
        
        # Check proper nouns
        if prompt_proper_nouns:
            # Calculate what percentage of proper nouns from prompt are missing in completion
            missing_proper_nouns = prompt_proper_nouns - completion_proper_nouns
            if missing_proper_nouns:
                missing_ratio = len(missing_proper_nouns) / len(prompt_proper_nouns)
                inconsistency_score += 0.4 * missing_ratio
        
        # Cap at 1.0
        return min(inconsistency_score, 1.0)
    
    def batch_analyze(
        self, 
        records: List[Dict[str, Any]], 
        include_completion: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Analyze a batch of completion records for hallucinations.
        
        Args:
            records: List of records with prompt/completion
            include_completion: Whether to include completion text in results
            
        Returns:
            Analysis results for each record
        """
        results = []
        
        for record in records:
            completion = record.get("completion", "")
            prompt = record.get("prompt", None)
            
            # Skip if no completion
            if not completion:
                continue
                
            # Analyze for hallucinations
            analysis = self.detect_hallucinations(completion, prompt, record)
            
            # Prepare result
            result = {
                "request_id": record.get("request_id", "unknown"),
                "timestamp": record.get("timestamp", datetime.now().isoformat()),
                "hallucination_detected": analysis["hallucination_detected"],
                "confidence": analysis["confidence"],
                "score": analysis["score"],
                "reasons": analysis["reasons"]
            }
            
            # Optionally include the completion text
            if include_completion:
                result["completion"] = completion
                
            results.append(result)
            
        return results