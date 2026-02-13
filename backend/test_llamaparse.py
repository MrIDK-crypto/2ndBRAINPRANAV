"""Quick test of LlamaParse"""
import os
from pathlib import Path

# Set API key
os.environ['LLAMA_CLOUD_API_KEY'] = os.getenv('LLAMA_CLOUD_API_KEY', '')

print("Testing LlamaParse...")

try:
    from llama_parse import LlamaParse
    print("✅ Import successful")

    # Initialize parser
    parser = LlamaParse(
        api_key=os.environ['LLAMA_CLOUD_API_KEY'],
        result_type="markdown",
        verbose=True
    )
    print("✅ Parser initialized")

    # Test with PDF
    test_file = "/Users/rishitjain/Downloads/Takeout/Google Chat/Groups/Space AAAAn7sv4eE/File-BEAT Healthcare Consulting Project Charter(3).pdf"

    if os.path.exists(test_file):
        print(f"\n📄 Testing: {Path(test_file).name}")
        print("⏳ Parsing (this may take 10-30 seconds)...")

        documents = parser.load_data(test_file)

        print(f"✅ Success! Extracted {len(documents)} document(s)")

        total_chars = sum(len(doc.text) for doc in documents)
        print(f"📊 Total characters: {total_chars:,}")

        if documents:
            print(f"\n📝 Preview (first 500 chars):")
            print("-" * 80)
            print(documents[0].text[:500])
            print("-" * 80)
    else:
        print(f"❌ Test file not found: {test_file}")

except ImportError as e:
    print(f"❌ Import failed: {e}")
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
