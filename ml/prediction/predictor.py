"""Inference engine for QRYVANTA hierarchical ticket classification with rule-based fallback."""

from pathlib import Path
from typing import Any, Dict, List, Optional
import joblib
import numpy as np

from ml.preprocessing.text_cleaner import combine_ticket_text
from ml.evaluation.evaluator import MIN_RELIABLE_SAMPLES_PER_CLASS


FALLBACK_KEYWORD_RULES: Dict[str, Dict[str, List[str]]] = {
    "Billing and Payments": {
        "Refund Request": ["refund", "money back", "reimburse", "credit back"],
        "Payment Failure": ["payment failed", "card declined", "transaction failed", "cannot pay", "checkout error"],
        "Incorrect Charge": ["overcharged", "double charged", "wrong amount", "unexpected charge", "invoice error", "billing error"],
    },
    "Technical Support": {
        "Application Error": ["crash", "500 error", "bug", "exception", "blank screen", "freeze", "not loading"],
        "Installation Issue": ["install", "setup failed", "installer", "dependency error", "cannot launch"],
        "Performance Issue": ["slow", "latency", "timeout", "lagging", "high cpu", "memory leak"],
    },
    "Account and Login": {
        "Password Reset": ["password", "reset link", "forgot password", "cannot sign in"],
        "Account Lockout": ["locked out", "suspended", "disabled account", "too many attempts"],
        "Verification Issue": ["2fa", "otp", "verification code", "mfa", "email verification"],
    },
    "Delivery and Shipping": {
        "Delayed Delivery": ["delayed", "late delivery", "still waiting", "past estimated"],
        "Missing Package": ["missing package", "never arrived", "lost shipment", "delivered but not received"],
        "Tracking Issue": ["tracking number", "tracking not updating", "stuck in transit", "carrier status"],
    },
    "Orders and Returns": {
        "Order Cancellation": ["cancel order", "cancellation", "stop shipment"],
        "Return Request": ["return item", "return label", "send back", "rma"],
        "Exchange Request": ["exchange", "wrong size", "swap item", "replace with"],
    },
    "Product Issues": {
        "Defective Item": ["defective", "broken", "damaged", "malfunctioning", "stopped working"],
        "Missing Parts": ["missing part", "incomplete box", "accessory missing"],
        "Quality Concern": ["poor quality", "scratched", "not as described"],
    },
    "Subscription Management": {
        "Plan Upgrade or Downgrade": ["upgrade plan", "downgrade", "change tier", "enterprise plan"],
        "Subscription Cancellation": ["cancel subscription", "auto-renew", "stop recurring", "unsubscribe"],
        "Seat or License Change": ["add seats", "license key", "user limit", "team members"],
    },
    "General Enquiries": {
        "Product Information": ["pricing", "features", "compatibility", "demo", "documentation"],
        "Policy Question": ["policy", "terms", "warranty", "privacy", "gdpr"],
        "Partnership or Feedback": ["feedback", "suggestion", "partner", "reseller"],
    },
}


class TicketClassifierPredictor:
    """Loads a versioned joblib model artifact and performs explainable inference."""

    def __init__(self, model_path: Optional[str] = None):
        self.model_path = model_path
        self.artifact: Optional[Dict[str, Any]] = None
        if model_path and Path(model_path).exists():
            self.load(model_path)

    def load(self, model_path: str) -> None:
        path = Path(model_path)
        if not path.exists():
            raise FileNotFoundError(f"Model artifact not found at {model_path}")
        self.artifact = joblib.load(path)
        self.model_path = str(path)

    @property
    def is_loaded(self) -> bool:
        return self.artifact is not None

    def _explain_tfidf_prediction(self, pipeline, clean_text: str, predicted_class: str) -> List[str]:
        """Extract top contributing positive TF-IDF terms for the predicted class."""
        try:
            vec = pipeline.named_steps["tfidf"]
            clf = pipeline.named_steps["clf"]
            classes = list(clf.classes_)
            if predicted_class not in classes:
                return []
            class_idx = classes.index(predicted_class)
            X_vec = vec.transform([clean_text])
            feature_names = vec.get_feature_names_out()
            if clf.coef_.shape[0] == 1:
                weights = clf.coef_[0] if class_idx == 1 else -clf.coef_[0]
            else:
                weights = clf.coef_[class_idx]
            contributions = X_vec.toarray()[0] * weights
            nonzero = np.where(contributions > 0)[0]
            if len(nonzero) == 0:
                return []
            top_indices = nonzero[np.argsort(contributions[nonzero])[::-1][:5]]
            return [str(feature_names[i]) for i in top_indices]
        except Exception:
            return []

    def _predict_fallback(self, subject: str, description: str) -> Dict[str, Any]:
        """Transparent rule-based fallback when no trained ML model artifact is active."""
        text = f"{subject} {description}".lower()
        scores: Dict[str, int] = {}
        best_sub: Dict[str, str] = {}

        for cat, sub_map in FALLBACK_KEYWORD_RULES.items():
            cat_score = 0
            top_sub_name = next(iter(sub_map.keys()))
            top_sub_hits = 0
            for sub_name, keywords in sub_map.items():
                hits = sum(1 for kw in keywords if kw in text)
                cat_score += hits
                if hits > top_sub_hits:
                    top_sub_hits = hits
                    top_sub_name = sub_name
            scores[cat] = cat_score
            best_sub[cat] = top_sub_name

        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        top_cat, top_hits = ranked[0]
        if top_hits == 0:
            top_cat = "General Enquiries"
            confidence = 0.35
            explanation = (
                "Rule-based fallback (no trained ML model active): no specific domain keywords matched; "
                "defaulted to General Enquiries for manual triage."
            )
        else:
            total_hits = max(sum(v for _, v in ranked), 1)
            confidence = round(min(0.45 + 0.30 * (top_hits / total_hits), 0.78), 4)
            explanation = (
                f"Rule-based fallback (no trained ML model active): matched {top_hits} keyword indicator(s) "
                f"for {top_cat} -> {best_sub[top_cat]}."
            )

        alternatives = [
            {"category": cat, "confidence": round(max(0.05, 0.3 * (hits / max(top_hits, 1))), 4)}
            for cat, hits in ranked[1:4]
            if hits > 0
        ]

        return {
            "category": top_cat,
            "subcategory": best_sub.get(top_cat),
            "confidence": confidence,
            "alternatives": alternatives,
            "explanation": explanation,
            "model_version": None,
            "prediction_source": "rule_based_fallback",
            "low_support_warning": None,
        }

    def predict(self, subject: str, description: str, product_reference: Optional[str] = None) -> Dict[str, Any]:
        """Predict main category, subcategory, confidence, alternatives, and transparent explanation."""
        clean_text = combine_ticket_text(subject, description, product_reference)
        if not clean_text or len(clean_text.strip()) < 3:
            raise ValueError("Ticket text must contain meaningful words for classification.")

        if not self.is_loaded or self.artifact is None:
            return self._predict_fallback(subject, description)

        main_pipe = self.artifact["main_pipeline"]
        probs = main_pipe.predict_proba([clean_text])[0]
        classes = list(main_pipe.named_steps["clf"].classes_)

        order = np.argsort(probs)[::-1]
        top_idx = int(order[0])
        predicted_cat = str(classes[top_idx])
        confidence = round(float(probs[top_idx]), 4)

        alternatives = [
            {"category": str(classes[int(i)]), "confidence": round(float(probs[int(i)]), 4)}
            for i in order[1:4]
        ]

        # Predict subcategory using hierarchical model
        sub_models = self.artifact.get("subcategory_models", {})
        predicted_sub: Optional[str] = None
        if predicted_cat in sub_models:
            entry = sub_models[predicted_cat]
            if entry["type"] == "constant":
                predicted_sub = str(entry["label"])
            else:
                predicted_sub = str(entry["pipeline"].predict([clean_text])[0])

        top_terms = self._explain_tfidf_prediction(main_pipe, clean_text, predicted_cat)
        train_counts = self.artifact.get("train_class_counts", {})
        support = int(train_counts.get(predicted_cat, 0))
        low_support_warning = None
        if support < MIN_RELIABLE_SAMPLES_PER_CLASS:
            low_support_warning = (
                f"Category '{predicted_cat}' had only {support} training examples; verify manually."
            )

        term_str = ", ".join(top_terms) if top_terms else "overall phrase distribution"
        explanation = (
            f"TF-IDF + Logistic Regression ({self.artifact.get('version')}) predicted "
            f"'{predicted_cat}'"
            + (f" / '{predicted_sub}'" if predicted_sub else "")
            + f" with {confidence * 100:.1f}% confidence based on key terms: {term_str}."
        )
        if low_support_warning:
            explanation += f" Warning: {low_support_warning}"

        return {
            "category": predicted_cat,
            "subcategory": predicted_sub,
            "confidence": confidence,
            "alternatives": alternatives,
            "explanation": explanation,
            "model_version": self.artifact.get("version"),
            "prediction_source": "ml_model",
            "low_support_warning": low_support_warning,
        }
