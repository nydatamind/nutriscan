# NutriScan · NY

### DEVELOPED BY NITIN YADAV

A production-ready, mobile-first NutriScan · NY application providing instant, deterministic food ingredient safety analysis, additive classification, category detection, and allergen alerts.

---

## Direct Android APK Download

The single, updated Android APK is available directly in the project root:
- [NutriScan.apk](NutriScan.apk) (Ready to install on Android devices)

---

## Key Capabilities

- Instant Camera and Gallery Scan: Capture or choose a label photo with automatic one-touch instant analysis.
- Smart Product Category Detection: Automatically classifies Food & Snacks, Skincare, Haircare & Personal Care, Household Products, and Medicines & Medical items.
- Deterministic Safety Grading (A to D): Fixed rule-based scoring (Grade A: Excellent, Grade B: Good, Grade C: Caution, Grade D: Hazardous).
- Formulation Benchmarks: Smart formulation standards that eliminate missing ingredient errors for non-food items.
- Detailed Risk Breakdown: Breakdown per ingredient with side effects, regulatory status, and INS / E-number mapping.
- Allergen Alert System: Highlights common allergens (Soy, Milk, Gluten, Nuts, Sulfites, etc.).
- Multi-Language Support: Seamless reporting in English, Hindi, and Hinglish.
- Fast Response Times: In-memory caching delivering sub-millisecond repeated queries.

---

## Quick Setup

### 1. Configure Environment Keys
Create a `.env` file in the root directory:
```env
GEMINI_API_KEY=AIzaSy...your_gemini_api_key
```

### 2. Run the App
```bash
streamlit run app.py
```

The app will launch at `http://localhost:8501`.

---

## Developer
DEVELOPED BY NITIN YADAV
