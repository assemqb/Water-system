"""
ollama_assistant.py
Универсальный AI assistant слой.
Работает с любым UI: Streamlit сейчас, FastAPI/React потом.
Запуск Ollama: ollama serve  (в отдельном терминале)
"""

import ollama
import json
import sqlite3
import pandas as pd
import numpy as np
from pathlib import Path


class WaterQualityAssistant:
    """
    AI assistant поверх ML системы.
    Данные не покидают машину — Ollama работает локально.
    """

    def __init__(self, model: str = "llama3.1",
                 db_path: str = "water_quality.db"):
        self.model   = model
        self.db_path = db_path
        self.system_prompt = """
You are an expert water quality analyst for Kazakhstan's 8 river basins.
You have access to real monitoring data from Kazhydromet covering 2001-2022,
supplemented by chemical pollution records (2020-2024) and WHO reference data.

Key facts about the system:
- WQI > 100 means average MPC threshold exceeded (dangerous)
- WQI 60-100 means moderate quality (monitor)
- WQI < 60 means good quality (safe)
- Hazard class 3 (ratio >= 2.0) requires immediate action
- The 8 basins: Balkash-Alakol, Ertis, Esil, Nura-Sarysu,
  Shu-Talas, Aral-Syrdarya, Tobyl-Torgay, Zhaiyk-Kaspian

Rules:
- Always cite specific numbers from the provided data
- Be concise and practical
- Answer in the same language as the question (Russian or English)
- If data is insufficient, say so explicitly
        """.strip()

    # ── ЗАГРУЗКА ДАННЫХ ───────────────────────────────────────
    def load_data(self) -> pd.DataFrame:
        """Загружает данные из SQLite или CSV."""
        if Path(self.db_path).exists():
            conn = sqlite3.connect(self.db_path)
            df = pd.read_sql("SELECT * FROM water_quality_data", conn)
            conn.close()
            return df
        csv_path = self.db_path.replace(".db", ".csv").replace(
            "water_quality", "combined_water_dataset"
        )
        if Path(csv_path).exists():
            return pd.read_csv(csv_path)
        raise FileNotFoundError(
            "Run combine_datasets.py first to create water_quality.db"
        )

    # ── КОНТЕКСТ ДЛЯ LLM ─────────────────────────────────────
    def build_context(self, df: pd.DataFrame = None,
                      filters: dict = None) -> dict:
        """
        Строит JSON-контекст из датафрейма.
        filters = {"region": "VKO", "year": 2022, "source": "Kazhydromet_Real"}
        """
        if df is None:
            df = self.load_data()

        # Применяем фильтры если есть
        if filters:
            if filters.get("region"):
                df = df[df["region"] == filters["region"]]
            if filters.get("basin"):
                df = df[df["basin"] == filters["basin"]]
            if filters.get("year"):
                df = df[df["year"] == filters["year"]]
            if filters.get("source"):
                df = df[df["source"] == filters["source"]]

        df_wqi = df[df["wqi_score"].notna()]

        # Региональный WQI
        regional = {}
        if "region" in df_wqi.columns:
            regional = (df_wqi.groupby("region")["wqi_score"]
                              .mean().round(2).to_dict())

        # Бассейновый WQI
        basin_wqi = {}
        if "basin" in df_wqi.columns:
            basin_wqi = (df_wqi.groupby("basin")["wqi_score"]
                               .mean().round(2).to_dict())

        # Тренд по годам
        yearly = {}
        if "year" in df_wqi.columns:
            yearly = (df_wqi.groupby("year")["wqi_score"]
                            .mean().round(2)
                            .dropna().to_dict())
            yearly = {int(k): v for k, v in yearly.items()}

        # Источники данных
        sources = {}
        if "source" in df.columns:
            sources = df["source"].value_counts().to_dict()

        worst  = max(regional, key=regional.get) if regional else "N/A"
        best   = min(regional, key=regional.get) if regional else "N/A"
        hr_pct = round((df_wqi["hazard_class"] == 3).mean() * 100, 1) \
                 if "hazard_class" in df_wqi.columns else 0

        return {
            "total_records":      len(df),
            "records_with_wqi":   len(df_wqi),
            "mean_wqi_overall":   round(df_wqi["wqi_score"].mean(), 2) if len(df_wqi) else None,
            "high_risk_percent":  hr_pct,
            "worst_region":       worst,
            "best_region":        best,
            "regional_wqi":       regional,
            "basin_wqi":          basin_wqi,
            "yearly_trend":       yearly,
            "data_sources":       sources,
            "active_filters":     filters or {},
        }

    # ── ОСНОВНОЙ МЕТОД ────────────────────────────────────────
    def analyze(self, question: str,
                context: dict = None,
                df: pd.DataFrame = None) -> str:
        """
        Главный метод — задаёшь вопрос, получаешь ответ.

        Использование:
            assistant = WaterQualityAssistant()
            answer = assistant.analyze("Какой регион самый загрязнённый?")
        """
        if context is None:
            context = self.build_context(df)

        context_str = json.dumps(context, ensure_ascii=False, indent=2)

        prompt = f"""
Current water quality analytics data:
{context_str}

User question: {question}

Provide a specific, data-driven answer:
        """.strip()

        try:
            response = ollama.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user",   "content": prompt},
                ],
                options={"temperature": 0.3},   # низкая температура = точнее
            )
            return response["message"]["content"]

        except Exception as e:
            return (
                f"⚠️ Ollama assistant unavailable.\n"
                f"Make sure Ollama is running: 'ollama serve'\n"
                f"Error: {str(e)}"
            )

    # ── БЫСТРЫЕ ГОТОВЫЕ ВОПРОСЫ ───────────────────────────────
    def quick_summary(self) -> str:
        """Автоматический отчёт по всем данным."""
        context = self.build_context()
        return self.analyze(
            "Give me a brief executive summary of water quality "
            "across all Kazakhstan basins. What are the top 3 concerns?",
            context
        )

    def risk_alert(self, region: str) -> str:
        """Анализ риска для конкретного региона."""
        context = self.build_context(filters={"region": region})
        return self.analyze(
            f"What is the current water quality risk level for {region}? "
            f"What specific actions should be taken?",
            context
        )

    def trend_analysis(self, basin: str) -> str:
        """Трендовый анализ по бассейну."""
        context = self.build_context(filters={"basin": basin})
        return self.analyze(
            f"Analyze the water quality trend for {basin} basin. "
            f"Is it improving or deteriorating?",
            context
        )


# ── ЗАПУСК ДЛЯ ПРОВЕРКИ ──────────────────────────────────────
if __name__ == "__main__":
    print("Testing WaterQualityAssistant...")
    print("Make sure 'ollama serve' is running in another terminal.\n")

    assistant = WaterQualityAssistant()

    try:
        df = assistant.load_data()
        print(f"✅ Data loaded: {len(df):,} rows\n")

        context = assistant.build_context(df)
        print("Context built:")
        print(json.dumps(context, ensure_ascii=False, indent=2))

        print("\n" + "="*50)
        print("Test question: Какой бассейн самый загрязнённый?")
        print("="*50)
        answer = assistant.analyze(
            "Какой бассейн самый загрязнённый и почему?",
            context
        )
        print(answer)

    except FileNotFoundError as e:
        print(f"❌ {e}")
        print("Run: python3 combine_datasets.py first")