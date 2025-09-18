"""
Question generator for active recall and comprehension testing.
"""

import random
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class Question:
    """Represents a question for active recall."""
    question_text: str
    answer: str
    question_type: str  # 'factual', 'conceptual', 'application', 'synthesis'
    difficulty: str  # 'easy', 'medium', 'hard'
    context: Optional[str] = None
    hints: List[str] = None


class QuestionGenerator:
    """
    Generate questions from text for active recall and comprehension testing.
    """

    def __init__(self):
        self.question_templates = {
            'factual': [
                "What is {concept}?",
                "Define {term}.",
                "Who {action}?",
                "When did {event} occur?",
                "List the main characteristics of {topic}."
            ],
            'conceptual': [
                "Explain the relationship between {concept1} and {concept2}.",
                "Why is {concept} important?",
                "What is the main idea of {topic}?",
                "How does {concept} work?",
                "Compare and contrast {item1} and {item2}."
            ],
            'application': [
                "How would you apply {concept} to {scenario}?",
                "Give an example of {concept} in practice.",
                "What would happen if {condition}?",
                "How could {concept} be used to solve {problem}?"
            ],
            'synthesis': [
                "What conclusions can you draw from {evidence}?",
                "How would you combine {concept1} and {concept2}?",
                "What pattern emerges from {data}?",
                "Predict the outcome if {scenario}."
            ]
        }

    def generate_from_text(self, text: str, num_questions: int = 5) -> List[Question]:
        """Generate questions from a text passage."""
        questions = []

        # Extract key information
        sentences = self._split_sentences(text)
        key_terms = self._extract_key_terms(text)
        facts = self._extract_facts(sentences)

        # Generate factual questions
        for fact in facts[:num_questions // 2]:
            question = self._create_factual_question(fact)
            if question:
                questions.append(question)

        # Generate conceptual questions
        for term in key_terms[:num_questions // 2]:
            question = self._create_conceptual_question(term, text)
            if question:
                questions.append(question)

        return questions[:num_questions]

    def generate_from_highlights(self, highlights: List[str]) -> List[Question]:
        """Generate questions from user highlights."""
        questions = []

        for highlight in highlights:
            # Determine what type of content this is
            if self._is_definition(highlight):
                question = self._create_definition_question(highlight)
            elif self._is_list(highlight):
                question = self._create_list_question(highlight)
            else:
                question = self._create_explanation_question(highlight)

            if question:
                questions.append(question)

        return questions

    def _create_factual_question(self, fact: str) -> Optional[Question]:
        """Create a factual question from a fact."""
        # Simple pattern matching for fact extraction
        patterns = [
            (r"(\w+) is (\w+)", "What is {0}?", "{1}"),
            (r"(\w+) was (\w+)", "What was {0}?", "{1}"),
            (r"In (\d+), (\w+)", "When did {1} occur?", "{0}"),
        ]

        for pattern, question_template, answer_template in patterns:
            match = re.search(pattern, fact, re.IGNORECASE)
            if match:
                groups = match.groups()
                return Question(
                    question_text=question_template.format(*groups),
                    answer=answer_template.format(*groups),
                    question_type='factual',
                    difficulty='easy',
                    context=fact
                )

        return None

    def _create_conceptual_question(self, term: str, context: str) -> Question:
        """Create a conceptual question about a term."""
        question_text = f"Explain the concept of {term} based on the text."

        # Extract sentences containing the term for the answer
        sentences = [s for s in context.split('.') if term.lower() in s.lower()]
        answer = ' '.join(sentences[:2]) if sentences else f"The text discusses {term}."

        return Question(
            question_text=question_text,
            answer=answer,
            question_type='conceptual',
            difficulty='medium',
            context=context[:200]
        )

    def _create_definition_question(self, highlight: str) -> Optional[Question]:
        """Create a question from a definition."""
        # Pattern: "X is defined as Y" or "X: Y"
        patterns = [
            r"(\w+) is defined as (.+)",
            r"(\w+) means (.+)",
            r"(\w+): (.+)"
        ]

        for pattern in patterns:
            match = re.search(pattern, highlight, re.IGNORECASE)
            if match:
                term, definition = match.groups()
                return Question(
                    question_text=f"Define {term}.",
                    answer=definition,
                    question_type='factual',
                    difficulty='easy',
                    context=highlight
                )

        return None

    def _create_list_question(self, highlight: str) -> Question:
        """Create a question from a list."""
        # Detect if highlight contains a list
        list_items = re.findall(r'[•\-\*]\s*(.+)', highlight)

        if list_items:
            return Question(
                question_text="List the main points mentioned.",
                answer='\n'.join(list_items),
                question_type='factual',
                difficulty='easy',
                context=highlight
            )

        return None

    def _create_explanation_question(self, highlight: str) -> Question:
        """Create an explanation question from a highlight."""
        # Extract the main subject
        first_sentence = highlight.split('.')[0]

        return Question(
            question_text=f"Explain the following concept: {first_sentence[:50]}...",
            answer=highlight,
            question_type='conceptual',
            difficulty='medium',
            context=highlight
        )

    def _is_definition(self, text: str) -> bool:
        """Check if text is a definition."""
        definition_patterns = [
            r'\bis defined as\b',
            r'\bmeans\b',
            r'\brefers to\b',
            r':\s*[A-Z]'  # Colon followed by capital letter
        ]
        return any(re.search(pattern, text, re.IGNORECASE) for pattern in definition_patterns)

    def _is_list(self, text: str) -> bool:
        """Check if text contains a list."""
        return bool(re.search(r'[•\-\*]\s*\w+', text))

    def _split_sentences(self, text: str) -> List[str]:
        """Split text into sentences."""
        sentences = re.split(r'[.!?]\s+', text)
        return [s.strip() for s in sentences if s.strip()]

    def _extract_key_terms(self, text: str) -> List[str]:
        """Extract key terms from text."""
        # Simple noun phrase extraction
        # In production, use NLP libraries like spaCy
        words = re.findall(r'\b[A-Z][a-z]+\b', text)
        return list(set(words))[:10]

    def _extract_facts(self, sentences: List[str]) -> List[str]:
        """Extract factual statements from sentences."""
        facts = []
        fact_patterns = [
            r'\bis\b',
            r'\bwas\b',
            r'\bare\b',
            r'\bwere\b',
            r'In \d+',
            r'\bdefined as\b'
        ]

        for sentence in sentences:
            if any(re.search(pattern, sentence) for pattern in fact_patterns):
                facts.append(sentence)

        return facts


class QuizBuilder:
    """
    Build and manage quizzes from questions.
    """

    def __init__(self):
        self.question_generator = QuestionGenerator()

    def create_quiz(self, questions: List[Question],
                   quiz_type: str = 'mixed',
                   num_questions: int = 10) -> Dict[str, Any]:
        """Create a quiz from questions."""
        if quiz_type == 'factual':
            filtered = [q for q in questions if q.question_type == 'factual']
        elif quiz_type == 'conceptual':
            filtered = [q for q in questions if q.question_type in ['conceptual', 'synthesis']]
        else:
            filtered = questions

        # Randomly select questions
        selected = random.sample(filtered, min(num_questions, len(filtered)))

        return {
            'quiz_id': self._generate_quiz_id(),
            'questions': [
                {
                    'id': i,
                    'question': q.question_text,
                    'type': q.question_type,
                    'difficulty': q.difficulty,
                    'hints': q.hints or []
                }
                for i, q in enumerate(selected)
            ],
            'answers': {
                i: q.answer for i, q in enumerate(selected)
            },
            'total_questions': len(selected)
        }

    def grade_quiz(self, quiz: Dict[str, Any],
                  responses: Dict[int, str]) -> Dict[str, Any]:
        """Grade a quiz based on responses."""
        correct = 0
        results = []

        for q_id, response in responses.items():
            correct_answer = quiz['answers'].get(q_id, '')
            is_correct = self._check_answer(response, correct_answer)

            if is_correct:
                correct += 1

            results.append({
                'question_id': q_id,
                'response': response,
                'correct_answer': correct_answer,
                'is_correct': is_correct
            })

        score = (correct / len(responses)) * 100 if responses else 0

        return {
            'score': score,
            'correct': correct,
            'total': len(responses),
            'results': results
        }

    def _check_answer(self, response: str, correct: str) -> bool:
        """Check if response matches correct answer (fuzzy matching)."""
        # Simple check - can be improved with NLP
        response_lower = response.lower().strip()
        correct_lower = correct.lower().strip()

        # Exact match
        if response_lower == correct_lower:
            return True

        # Check if key terms are present
        key_terms = re.findall(r'\b\w+\b', correct_lower)
        important_terms = [t for t in key_terms if len(t) > 4]

        if important_terms:
            matches = sum(1 for term in important_terms if term in response_lower)
            return matches >= len(important_terms) * 0.6

        return False

    def _generate_quiz_id(self) -> str:
        """Generate unique quiz ID."""
        import hashlib
        from datetime import datetime
        timestamp = datetime.now().isoformat()
        return hashlib.md5(timestamp.encode()).hexdigest()[:8]