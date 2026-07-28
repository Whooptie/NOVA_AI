# test_episode_logica.py
# Los testscript, GEEN onderdeel van Nova's daemon.
# Test de nieuwe "nieuwe episode"-logica van weerwaarschuwing() zonder
# een echte API-call te doen -- roept weerwaarschuwing() rechtstreeks aan
# met verzonnen scenario's, net als test_weerwaarschuwing.py al deed.
#
# LET OP: dit script gebruikt je ECHTE data/weather_history.json, dus het
# schrijft er ook echt in weg. Maak gerust eerst een kopie van dat bestand
# als je 'm wil kunnen terugzetten na het testen.

from modules.weather.weather import WeatherModule


class DummyBus:
    """Vervangt de echte EventBus -- vangt publish()-aanroepen op zodat we
    kunnen zien wat er 'gezegd' zou worden, zonder dat iets echt print."""
    def subscribe(self, *args, **kwargs):
        pass

    def publish(self, event, data):
        print(f"   >>> ZOU PUBLICEREN op '{event}': {data['text']}")


def simuleer(weer_module, stad, main_cat, wind=5, temp=15, neerslag=False, label=""):
    """Bootst 1 check van check_proactieve_waarschuwing() na voor een
    verzonnen weersituatie, zonder de echte OpenWeatherMap-API aan te
    roepen."""
    waarschuwing = weer_module.weerwaarschuwing(
        main_cat, windsnelheid=wind, temperatuur=temp, heeft_neerslag=neerslag
    )

    if not waarschuwing:
        weer_module._markeer_status(stad, waarschuwing_tekst=None)
        print(f"[{label}] geen waarschuwing -> niets gemeld")
        return

    if not weer_module._is_nieuwe_episode(stad, waarschuwing):
        print(f"[{label}] waarschuwing ({waarschuwing!r}) -> NIET gemeld (zelfde episode)")
        return

    weer_module._markeer_status(stad, waarschuwing_tekst=waarschuwing)
    print(f"[{label}] waarschuwing ({waarschuwing!r}) -> WEL gemeld:")


if __name__ == "__main__":
    bus = DummyBus()
    # api_key mag hier "dummy" zijn: we roepen nooit de echte API aan in dit
    # testscript, enkel weerwaarschuwing() en de opslag-methodes zelf.
    weer = WeatherModule(bus, api_key="dummy")

    stad = "Aartrijke"

    print("=== Scenario: Kevin se vraag -- ochtend onweer, rustige middag, avond onweer terug ===\n")
    simuleer(weer, stad, "Thunderstorm", label="09u -- onweer")
    simuleer(weer, stad, "Thunderstorm", label="09u30 -- nog steeds onweer (zelfde check-interval)")
    simuleer(weer, stad, "Clear", label="13u -- rustig geworden")
    simuleer(weer, stad, "Thunderstorm", label="19u -- onweer terug")
    simuleer(weer, stad, "Snow", label="21u -- nu sneeuw i.p.v. onweer")
    simuleer(weer, stad, "Snow", label="21u30 -- nog steeds sneeuw")
    simuleer(weer, stad, "Clear", label="23u -- rustig")

    print("\nControleer nu 'data/weather_history.json' -- daar moet per stad")
    print("een veld 'laatste_waarschuwing_tekst' bijstaan (of null).")