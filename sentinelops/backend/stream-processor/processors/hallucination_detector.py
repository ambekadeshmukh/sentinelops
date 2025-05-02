# sentinelops/backend/stream-processor/processors/hallucination_detector.py
import re
import logging
import json
from typing import Dict, Any, List, Tuple, Optional, Union
import numpy as np
from datetime import datetime
from collections import defaultdict

logger = logging.getLogger(__name__)

class HallucinationDetector:
    """
    Enhanced service for detecting hallucinations in LLM outputs.
    
    This service uses multiple detection strategies:
    1. Heuristic detection (uncertainty markers, self-contradiction)
    2. Content inconsistency detection
    3. Factual verification
    4. Language pattern analysis
    5. Input-output semantic coherence
    """
    
    def __init__(self, confidence_threshold: float = 0.3):
        # Initialize detector with patterns and thresholds
        self.confidence_threshold = confidence_threshold
        self._init_patterns()
        self._load_factual_knowledge()
        
        # Cache previous detections for continuous learning
        self.detection_history = []
        self.max_history = 1000
    
    def _init_patterns(self):
        """Initialize detection patterns."""
        # Phrases indicating uncertainty or fabrication
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
        
        # Model self-reference patterns
        self.self_reference_patterns = [
            r"as an AI",
            r"as a language model",
            r"as an assistant",
            r"I was trained",
            r"my training",
            r"my knowledge",
            r"my training data",
            r"my last update",
            r"I don't have the ability to",
            r"I cannot access",
            r"I cannot browse",
            r"I cannot search"
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
        
        # Inconsistency markers in language
        self.inconsistency_markers = [
            r"on the other hand",
            r"however",
            r"despite",
            r"contrary to",
            r"actually",
            r"in fact",
            r"although",
            r"nonetheless",
            r"regardless",
            r"even though",
            r"while"
        ]
        
        # Definitive language patterns
        self.definitive_language = [
            r"\bdefinitely\b",
            r"\bcertainly\b",
            r"\babsolutely\b",
            r"\bundoubtedly\b",
            r"\bguaranteed\b",
            r"\bwithout a doubt\b",
            r"\bclearly\b",
            r"\bobviously\b"
        ]
    
    def _load_factual_knowledge(self):
        """Load factual knowledge for verification."""
        # Simple factual verification patterns 
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
        
        # Entity relationships for simple knowledge graph verification
        self.entity_relationships = {
            # Format: entity -> {attribute: value}
            "barack obama": {
                "profession": ["politician", "former president", "president"],
                "nationality": ["american", "us", "usa", "united states"],
                "spouse": ["michelle obama"]
            },
            "eiffel tower": {
                "location": ["paris", "france"],
                "built": ["1889"]
            },
            "albert einstein": {
                "profession": ["physicist", "scientist"],
                "theory": ["relativity", "general relativity", "special relativity"]
            }
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
                "confidence": "none",
                "reasons": [],
                "score": 0.0,
                "component_scores": {
                    "uncertainty": 0.0,
                    "contradiction": 0.0,
                    "factual_error": 0.0,
                    "prompt_inconsistency": 0.0,
                    "language_patterns": 0.0
                }
            }
            
        # Convert to lowercase for pattern matching
        completion_lower = completion.lower()
        
        # Scores and reasons
        hallucination_score = 0.0
        uncertainty_score = 0.0
        contradiction_score = 0.0
        factual_error_score = 0.0
        prompt_inconsistency_score = 0.0
        language_patterns_score = 0.0
        reasons = []
        
        # 1. Check for explicit uncertainty phrases
        detected_uncertainty_phrases = []
        for phrase in self.uncertainty_phrases:
            matches = re.finditer(phrase, completion_lower, re.IGNORECASE)
            for match in matches:
                detected_uncertainty_phrases.append({
                    "phrase": match.group(0),
                    "position": match.start()
                })
        
        if detected_uncertainty_phrases:
            # Weight by position - phrases at beginning are more significant
            total_weight = 0
            weighted_sum = 0
            
            for phrase_data in detected_uncertainty_phrases[:5]:  # Limit to top 5
                # Inverse position weight - earlier phrases have more weight
                position = phrase_data["position"]
                text_length = len(completion)
                position_weight = 1.0 - (position / text_length) if text_length > 0 else 0.5
                
                total_weight += position_weight
                weighted_sum += position_weight
            
            # Normalize the score
            if total_weight > 0:
                uncertainty_score += 0.4 * min(weighted_sum / total_weight, 1.0)
            else:
                uncertainty_score += 0.2  # Base score for having any phrases
                
            reasons.append({
                "type": "uncertainty_phrases",
                "details": [p["phrase"] for p in detected_uncertainty_phrases[:3]]  # Limit to top 3
            })
        
        # 2. Check for uncertainty markers
        uncertainty_marker_count = 0
        uncertainty_marker_positions = []
        
        for marker in self.uncertainty_markers:
            matches = re.finditer(marker, completion_lower, re.IGNORECASE)
            for match in matches:
                uncertainty_marker_count += 1
                uncertainty_marker_positions.append(match.start())
        
        # Calculate normalized score based on length and marker count
        if uncertainty_marker_count > 0:
            # Normalize by length of text
            words = len(completion.split())
            normalized_count = uncertainty_marker_count / (words / 100)  # Per 100 words
            
            # Analyze distribution of markers
            if uncertainty_marker_positions:
                # Calculate standard deviation of positions
                positions_array = np.array(uncertainty_marker_positions)
                positions_std = np.std(positions_array) if len(positions_array) > 1 else 0
                text_length = len(completion)
                
                # If markers are clustered (low std dev), it's more indicative of hallucination
                std_ratio = positions_std / text_length if text_length > 0 else 0.5
                
                distribution_factor = 1.0 - min(std_ratio * 3, 0.9)  # Lower std gives higher factor
                
                if normalized_count > 2:  # More than 2 markers per 100 words
                    uncertainty_score += 0.3 * min(normalized_count / 5, 1.0) * distribution_factor
                    reasons.append({
                        "type": "high_uncertainty_markers",
                        "count": uncertainty_marker_count,
                        "normalized_count": round(normalized_count, 2),
                        "distribution_factor": round(distribution_factor, 2)
                    })
        
        # 3. Check for self-references which often precede hallucinations
        self_reference_count = 0
        for pattern in self.self_reference_patterns:
            matches = re.finditer(pattern, completion_lower, re.IGNORECASE)
            for match in matches:
                self_reference_count += 1
        
        if self_reference_count > 0:
            # Normalize and add to uncertainty score
            normalized_self_refs = min(self_reference_count / 3, 1.0)  # Cap at 3 references
            uncertainty_score += 0.1 * normalized_self_refs
            
            if self_reference_count >= 2:
                reasons.append({
                    "type": "model_self_references",
                    "count": self_reference_count
                })
        
        # 4. Check for self-contradictions
        contradictions = self._detect_contradictions(completion)
        if contradictions:
            contradiction_score = 0.6 * min(len(contradictions), 3) / 3.0
            reasons.append({
                "type": "contradictions",
                "details": contradictions[:3]  # Limit to top 3
            })
        
        # 5. Check for factual errors
        factual_errors = self._check_factual_accuracy(completion_lower)
        if factual_errors:
            factual_error_score = 0.8  # High confidence if we detect a factual error
            reasons.append({
                "type": "factual_errors",
                "details": factual_errors
            })
        
        # 6. Check for prompt-completion inconsistency if prompt is available
        if prompt:
            prompt_inconsistency_score = self._check_prompt_inconsistency(prompt, completion)
            if prompt_inconsistency_score > 0.3:
                reasons.append({
                    "type": "prompt_inconsistency",
                    "score": round(prompt_inconsistency_score, 2)
                })
        
        # 7. Check for language pattern anomalies
        language_patterns_score = self._analyze_language_patterns(completion)
        if language_patterns_score > 0.3:
            reasons.append({
                "type": "unusual_language_patterns",
                "score": round(language_patterns_score, 2)
            })
        
        # Calculate overall hallucination score - weighted average
        component_scores = {
            "uncertainty": uncertainty_score,
            "contradiction": contradiction_score,
            "factual_error": factual_error_score,
            "prompt_inconsistency": prompt_inconsistency_score,
            "language_patterns": language_patterns_score
        }
        
        # Weights for different components
        weights = {
            "uncertainty": 0.2,
            "contradiction": 0.25,
            "factual_error": 0.3,
            "prompt_inconsistency": 0.15,
            "language_patterns": 0.1
        }
        
        # Calculate weighted score
        hallucination_score = sum(
            score * weights[component] 
            for component, score in component_scores.items()
        )
        
        # Also consider the max score for any component
        max_component_score = max(component_scores.values())
        
        # Blend weighted average with max score
        hallucination_score = 0.7 * hallucination_score + 0.3 * max_component_score
        
        # Determine confidence level
        confidence = "none"
        if hallucination_score >= 0.7:
            confidence = "high"
        elif hallucination_score >= 0.5:
            confidence = "medium"
        elif hallucination_score >= 0.3:
            confidence = "low"
        
        # Store detection in history for continuous learning
        self._update_detection_history({
            "completion_length": len(completion),
            "prompt_length": len(prompt) if prompt else 0,
            "score": hallucination_score,
            "confidence": confidence,
            "component_scores": component_scores,
            "timestamp": datetime.now()
        })
        
        return {
            "hallucination_detected": hallucination_score >= self.confidence_threshold,
            "confidence": confidence,
            "reasons": reasons,
            "score": round(hallucination_score, 2),
            "component_scores": {k: round(v, 2) for k, v in component_scores.items()}
        }
    
    def _update_detection_history(self, detection: Dict[str, Any]) -> None:
        """Update detection history for continuous learning."""
        self.detection_history.append(detection)
        
        # Trim if needed
        if len(self.detection_history) > self.max_history:
            self.detection_history = self.detection_history[-self.max_history:]
    
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
                            "pattern": f"{pos_pattern} vs {neg_pattern}"
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
                        
                # Check for entity-based contradictions
                entities_i = self._extract_entities(sentences[i])
                entities_j = self._extract_entities(sentences[j])
                
                # Find common entities
                common_entities = set(entities_i) & set(entities_j)
                
                for entity in common_entities:
                    # Check for contradictory attributes
                    attrs_i = self._extract_attributes(entity, sentences[i])
                    attrs_j = self._extract_attributes(entity, sentences[j])
                    
                    # Find contradictory attributes
                    for attr in attrs_i:
                        if attr in attrs_j and attrs_i[attr] != attrs_j[attr]:
                            contradictions.append({
                                "sentence1": sentences[i],
                                "sentence2": sentences[j],
                                "entity": entity,
                                "attribute": attr,
                                "value1": attrs_i[attr],
                                "value2": attrs_j[attr]
                            })
        
        return contradictions
    
    def _extract_entities(self, text: str) -> List[str]:
        """
        Extract potential entities from text using simple heuristics.
        
        Args:
            text: The text to analyze
            
        Returns:
            List of potential entities
        """
        # Simple rule-based entity extraction (proper nouns)
        entities = []
        
        # Proper nouns (capitalized words not at the start of sentences)
        proper_nouns = re.findall(r'(?<=[.!?]\s+|\s+)[A-Z][a-z]+', text)
        entities.extend(proper_nouns)
        
        # Known entities from our knowledge base
        for entity in self.entity_relationships:
            if entity in text.lower():
                entities.append(entity)
        
        return entities
    
    def _extract_attributes(self, entity: str, text: str) -> Dict[str, str]:
        """
        Extract attributes for an entity from text.
        
        Args:
            entity: The entity to extract attributes for
            text: The text to analyze
            
        Returns:
            Dictionary of attribute -> value
        """
        attributes = {}
        
        # Simple patterns for attribute extraction
        patterns = [
            (r'(?i)' + re.escape(entity) + r'[^\.\?!]*\bis\b[^\.\?!]*?(\w+)', 'is'),
            (r'(?i)' + re.escape(entity) + r'[^\.\?!]*\bhas\b[^\.\?!]*?(\w+)', 'has'),
            (r'(?i)' + re.escape(entity) + r'[^\.\?!]*\bwas\b[^\.\?!]*?(\w+)', 'was'),
            (r'(?i)' + re.escape(entity) + r'[^\.\?!]*\bin\b[^\.\?!]*?(\w+)', 'location')
        ]
        
        for pattern, attr_name in patterns:
            matches = re.findall(pattern, text)
            if matches:
                attributes[attr_name] = matches[0]
        
        return attributes
    
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
        
        # Check knowledge graph relationships
        for entity, attributes in self.entity_relationships.items():
            if entity in text:
                # Check for incorrect attributes
                for attr, valid_values in attributes.items():
                    # Look for statements about this attribute
                    attr_patterns = [
                        r'(?i)' + re.escape(entity) + r'[^\.\?!]*\b' + re.escape(attr) + r'\b[^\.\?!]*?(\w+)',
                        r'(?i)' + re.escape(entity) + r'[\s\w]*\b(?:is|was|as)\b[\s\w]*\b' + re.escape(attr) + r'\b'
                    ]
                    
                    for pattern in attr_patterns:
                        matches = re.finditer(pattern, text)
                        for match in matches:
                            attr_value = match.group(1) if len(match.groups()) > 0 else ""
                            attr_text = match.group(0)
                            
                            # Check if attribute value is valid
                            valid = False
                            for valid_value in valid_values:
                                if valid_value in attr_text.lower():
                                    valid = True
                                    break
                            
                            if not valid and attr_text:
                                errors.append({
                                    "text": attr_text,
                                    "entity": entity,
                                    "attribute": attr,
                                    "expected": ", ".join(valid_values),
                                    "reason": "incorrect factual relationship"
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
        
        # Check for direct questions that aren't answered
        # Look for question words
        question_words = ["who", "what", "where", "when", "why", "how", "can", "does", "is", "are", "will", "should"]
        questions = re.findall(r'(?i)(?:^|\. |[\n\r])(' + '|'.join(question_words) + r')[^.!?]*\?', prompt)
        
        if questions:
            # Simple heuristic: check if completion contains words from the questions
            answered_questions = 0
            for question in questions:
                # Extract key words from question
                key_words = set(re.findall(r'\b\w{4,}\b', question.lower()))
                key_words = key_words - set(question_words) - set(["this", "that", "these", "those", "about", "would"])
                
                # Check if any key words appear in completion
                for word in key_words:
                    if word in completion_lower:
                        answered_questions += 1
                        break
            
            if len(questions) > 0:
                answer_ratio = answered_questions / len(questions)
                unanswered_score = 0.5 * (1.0 - answer_ratio)
                inconsistency_score += unanswered_score
        
        # Cap at 1.0
        return min(inconsistency_score, 1.0)
    
    def _analyze_language_patterns(self, text: str) -> float:
        """
        Analyze language patterns for signs of hallucination.
        
        Args:
            text: The text to analyze
            
        Returns:
            A score indicating hallucination likelihood based on language patterns
        """
        pattern_score = 0.0
        total_sentences = len(re.split(r'[.!?]\s+', text))
        
        if total_sentences < 3:
            return 0.0  # Not enough text to analyze
        
        # Check for inconsistency markers
        inconsistency_count = 0
        for marker in self.inconsistency_markers:
            inconsistency_count += len(re.findall(marker, text.lower()))
        
        # More than 1 inconsistency marker per 3 sentences suggests potential hallucination
        if inconsistency_count > total_sentences / 3:
            pattern_score += 0.2
        
        # Check for mix of definitive and uncertain language
        definitive_count = 0
        for pattern in self.definitive_language:
            definitive_count += len(re.findall(pattern, text.lower()))
        
        uncertainty_count = 0
        for marker in self.uncertainty_markers:
            uncertainty_count += len(re.findall(marker, text.lower()))
        
        # Having both definitive and uncertain language is a potential red flag
        if definitive_count > 0 and uncertainty_count > 0:
            # Calculate ratio
            smaller_count = min(definitive_count, uncertainty_count)
            larger_count = max(definitive_count, uncertainty_count)
            
            if larger_count > 0:
                language_inconsistency_ratio = smaller_count / larger_count
                
                # Higher score for more balanced mixture (closer to 1.0 ratio)
                pattern_score += 0.3 * language_inconsistency_ratio
        
        # Check for unnaturally balanced structure (e.g., listing pros and cons with exactly the same number)
        # This can be a sign of fabrication
        balanced_structure_score = self._check_balanced_structure(text)
        pattern_score += balanced_structure_score
        
        return min(pattern_score, 1.0)
    
    def _check_balanced_structure(self, text: str) -> float:
        """
        Check for unnaturally balanced structure in text.
        
        Args:
            text: The text to analyze
            
        Returns:
            A score for balanced structure likelihood
        """
        # Look for bulleted or numbered lists
        list_pattern = r'(?:\d+\.|\*|\-)\s+([^\n]+)'
        list_items = re.findall(list_pattern, text)
        
        if len(list_items) < 4:
            return 0.0  # Not enough list items
        
        # Check for balanced lists (pros/cons, advantages/disadvantages)
        section_markers = [
            ("pros", "cons"),
            ("advantages", "disadvantages"),
            ("benefits", "drawbacks"),
            ("strengths", "weaknesses"),
            ("positive", "negative")
        ]
        
        # Extract sections between these markers
        for pos_marker, neg_marker in section_markers:
            pos_pattern = r'(?i)' + re.escape(pos_marker) + r'[^:]*:(.*?)(?:' + re.escape(neg_marker) + r'|$)'
            neg_pattern = r'(?i)' + re.escape(neg_marker) + r'[^:]*:(.*?)(?:$)'
            
            pos_section = re.search(pos_pattern, text, re.DOTALL)
            neg_section = re.search(neg_pattern, text, re.DOTALL)
            
            if pos_section and neg_section:
                # Count list items in each section
                pos_items = re.findall(list_pattern, pos_section.group(1))
                neg_items = re.findall(list_pattern, neg_section.group(1))
                
                # If both have list items and counts are very close, it may be fabricated
                if pos_items and neg_items:
                    if abs(len(pos_items) - len(neg_items)) <= 1:
                        return 0.3  # Suspiciously balanced
        
        return 0.0
    
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
                "component_scores": analysis["component_scores"],
                "reasons": analysis["reasons"]
            }
            
            # Optionally include the completion text
            if include_completion:
                result["completion"] = completion
                
            results.append(result)
            
        return results
    
    def analyze_trends(self) -> Dict[str, Any]:
        """
        Analyze trends in hallucination detection.
        
        Returns:
            Dictionary with trend analysis
        """
        if not self.detection_history or len(self.detection_history) < 10:
            return {
                "enough_data": False,
                "message": "Not enough data for trend analysis"
            }
        
        # Calculate average scores over time
        avg_scores = []
        window_size = min(10, len(self.detection_history) // 5)
        
        for i in range(0, len(self.detection_history), window_size):
            window = self.detection_history[i:i+window_size]
            avg_score = sum(d["score"] for d in window) / len(window)
            avg_scores.append({
                "window_index": i // window_size,
                "avg_score": avg_score
            })
        
        # Calculate trend
        if len(avg_scores) >= 2:
            first_avg = avg_scores[0]["avg_score"]
            last_avg = avg_scores[-1]["avg_score"]
            score_change = last_avg - first_avg
            
            trend_direction = "increasing" if score_change > 0.1 else "decreasing" if score_change < -0.1 else "stable"
            
            return {
                "enough_data": True,
                "trend": trend_direction,
                "score_change": score_change,
                "windows": avg_scores,
                "component_trends": self._analyze_component_trends()
            }
        
        return {
            "enough_data": False,
            "message": "Not enough windows for trend analysis"
        }
    
    def _analyze_component_trends(self) -> Dict[str, str]:
        """
        Analyze trends in individual hallucination components.
        
        Returns:
            Dictionary of component trends
        """
        component_trends = {}
        
        if not self.detection_history or len(self.detection_history) < 10:
            return component_trends
        
        # Get components from the first entry
        components = list(self.detection_history[0]["component_scores"].keys())
        
        for component in components:
            # Calculate early and recent averages
            split_point = len(self.detection_history) // 2
            
            early_scores = [
                d["component_scores"].get(component, 0) 
                for d in self.detection_history[:split_point]
            ]
            
            recent_scores = [
                d["component_scores"].get(component, 0) 
                for d in self.detection_history[split_point:]
            ]
            
            if early_scores and recent_scores:
                early_avg = sum(early_scores) / len(early_scores)
                recent_avg = sum(recent_scores) / len(recent_scores)
                
                change = recent_avg - early_avg
                
                if change > 0.1:
                    component_trends[component] = "increasing"
                elif change < -0.1:
                    component_trends[component] = "decreasing"
                else:
                    component_trends[component] = "stable"
        
        return component_trends                            