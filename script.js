// Beispieldaten – hier kannst du weitere Charaktere ergänzen.
const characters = [
  {
    name: "Lightning McQueen",
    type: "Rennwagen",
    image: "https://lumiere-a.akamaihd.net/v1/images/lightningmcqueen_characterbio_2bd07a1c_78f6b425.jpeg?region=0%2C0%2C600%2C600",
    description: "Der rote Rennwagen mit der Startnummer 95."
  },
  {
    name: "Hook",
    type: "Abschleppwagen",
    image: "https://lumiere-a.akamaihd.net/v1/images/mater_characterimage_b6ea14ea.jpeg?region=0%2C0%2C600%2C600",
    description: "McQueens bester Freund aus Radiator Springs."
  },
  {
    name: "Sally",
    type: "Sportwagen",
    image: "https://lumiere-a.akamaihd.net/v1/images/sally_characterimage_a07777b2_500c151b.jpeg?region=0%2C0%2C600%2C600",
    description: "Die blaue Porsche-Dame aus Radiator Springs."
  },
  {
    name: "Doc Hudson",
    type: "Rennlegende",
    image: "https://lumiere-a.akamaihd.net/v1/images/cars_dochudson_characterimage_829445c8.jpeg?region=0%2C0%2C600%2C600",
    description: "Ein erfahrener Rennfahrer und McQueens Mentor."
  }
];

const search = document.getElementById("search");
const cards = document.getElementById("cards");
const status = document.getElementById("status");
const template = document.getElementById("card-template");

function renderCharacters() {
  const query = search.value.trim().toLocaleLowerCase("de");

  const results = characters.filter(character => {
    const text = `${character.name} ${character.type}`;
    return text.toLocaleLowerCase("de").includes(query);
  });

  cards.replaceChildren();

  results.forEach(character => {
    const card = template.content.cloneNode(true);

    const image = card.querySelector(".character-image");
    const fallback = card.querySelector(".image-fallback");
    image.alt = character.name;
    image.addEventListener("error", () => {
      image.hidden = true;
      fallback.hidden = false;
    }, { once: true });
    image.src = character.image;
    card.querySelector("h2").textContent = character.name;
    card.querySelector(".badge").textContent = character.type;
    card.querySelector(".description").textContent = character.description;

    cards.appendChild(card);
  });

  status.textContent = results.length === 0
    ? "Keine Charaktere gefunden. Versuche einen anderen Suchbegriff."
    : `${results.length} Charakter${results.length === 1 ? "" : "e"} gefunden.`;
}

search.addEventListener("input", renderCharacters);
renderCharacters();
