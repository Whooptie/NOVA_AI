from identity.blueprint.loader import load_identity_blueprint
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

def test_identity_loader():
    print("🔍 Identity loader test gestart...")

    try:
        blueprint = load_identity_blueprint()
        print("🎉 Test geslaagd!")
        print(f"Naam: {blueprint.get('name')}")
        print(f"Leeftijd: {blueprint.get('age')}")
        print(f"Baseline mood: {blueprint['emotional_profile']['baseline_mood']}")
    except Exception as e:
        print("❌ Test mislukt!")
        print(e)

if __name__ == "__main__":
    test_identity_loader()
