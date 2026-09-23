// Beispieldaten – hier kannst du weitere Charaktere ergänzen.
const characters = [
  {
    name: "Lightning McQueen",
    type: "Rennwagen",
    emoji: "🏎️",
    description: "Der rote Rennwagen mit der Startnummer 95."
  },
  {
    name: "Hook",
    type: "Abschleppwagen",
    emoji: "🛻",
    description: "McQueens bester Freund aus Radiator Springs."
  },
  {
    name: "Sally",
    type: "Sportwagen",
    emoji: "🚙",
    description: "Die blaue Porsche-Dame aus Radiator Springs."
  },
  {
    name: "Doc Hudson",
    type: "Rennlegende",
    emoji: "🚘",
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

    card.querySelector(".card-banner").textContent = character.emoji;
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