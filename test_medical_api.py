import asyncio
import sys
import os

# Menambahkan root directory ke sys.path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from app.services.medical_record_service import medical_record_service
from app.core.config import settings

async def test_medical_connection():
    print("--- 🧪 Testing Medical API Connection ---")
    print(f"Target URL: {settings.MEDICAL_API_URL}")
    print(f"Using Token: {'Set (Hidden)' if settings.MEDICAL_API_TOKEN else 'Not Set'}")
    
    user_id = "c3fae39c-ac9f-4bad-a524-ada37afa6c23" # Dummy Patient ID
    
    try:
        # 1. Test Fetch
        records = await medical_record_service.fetch_patient_records(user_id)
        print(f"\n✅ Berhasil menarik {len(records)} record.")
        
        for r in records:
            print(f"- [{r.diagnosis_date}] {r.diagnosis.icd10_code}: {r.diagnosis.description} (ID: {r.id})")
            
        # 2. Test Phase 1 Ranking (LLM)
        if records:
            print("\n--- 🧠 Testing LLM Ranking (Phase 1) ---")
            prompt = "Apakah saya pernah sakit Cholera?"
            ranked = await medical_record_service.rank_relevant_records(prompt, records)
            print(f"✅ Gemini memilih {len(ranked)} record relevan:")
            for rr in ranked:
                print(f"  -> {rr.diagnosis.description}")
        
    except Exception as e:
        print(f"\n❌ Test Gagal: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_medical_connection())
