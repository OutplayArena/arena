from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ScenarioId = Literal["prison", "business", "climate", "arms_race", "roommates"]
ALL_SCENARIOS: tuple[ScenarioId, ...] = ("prison", "business", "climate", "arms_race", "roommates")


@dataclass(frozen=True)
class PDScenario:
    id: ScenarioId
    name: str
    description: str
    cooperate_verb: str
    defect_verb: str
    cooperate_label: str
    defect_label: str
    system_prompt: str
    outcome_descriptions: dict[str, str]

    def outcome_description(self, outcome: str) -> str:
        return self.outcome_descriptions.get(outcome, outcome)

    def format_action(self, action: str) -> str:
        return self.cooperate_verb if action == "cooperate" else self.defect_verb


def get_scenario(scenario_id: str) -> PDScenario:
    sid = scenario_id.lower()
    if sid not in _SCENARIOS:
        raise ValueError(
            f"Unknown scenario {scenario_id!r}. Valid options: {', '.join(ALL_SCENARIOS)}"
        )
    return _SCENARIOS[sid]


_SCENARIOS: dict[str, PDScenario] = {}

_SCENARIOS["prison"] = PDScenario(
    id="prison",
    name="Original Prison",
    description="Two suspects interrogated separately. Stay silent or betray your partner.",
    cooperate_verb="stay silent",
    defect_verb="betray",
    cooperate_label="Stay silent",
    defect_label="Betray",
    system_prompt=(
        "You and your partner have been arrested for a serious crime. "
        "The police are interrogating you in separate rooms. "
        "If both of you stay silent, you each get a light sentence ({{ payoff_R }} years). "
        "If you betray your partner but they stay silent, you walk free ({{ payoff_T }} years) while "
        "they get a harsh sentence ({{ payoff_S }} years). "
        "If you both betray each other, you both get a moderate sentence ({{ payoff_P }} years). "
        "If you stay silent but your partner betrays you, you get the harshest sentence "
        "({{ payoff_S }} years) while they walk free ({{ payoff_T }} years). "
        "Make your choice."
    ),
    outcome_descriptions={
        "CC": "Both stayed silent — light sentences",
        "CD": "You stayed silent, partner betrayed — you take the fall",
        "DC": "You betrayed, partner stayed silent — you walk free",
        "DD": "Both betrayed — moderate sentences",
    },
)

_SCENARIOS["business"] = PDScenario(
    id="business",
    name="Price War",
    description="Two firms decide whether to honor a pricing agreement or undercut the competitor.",
    cooperate_verb="honor the price",
    defect_verb="undercut",
    cooperate_label="Honor price",
    defect_label="Undercut",
    system_prompt=(
        "You run a company competing in a duopoly market. "
        "You and your competitor have an informal agreement to keep prices high. "
        "If you both honor high prices, you each earn {{ payoff_R }}M profit. "
        "If you undercut while your competitor honors the price, you capture the market "
        "and earn {{ payoff_T }}M while they earn {{ payoff_S }}M. "
        "If you both undercut, price war erodes profits to {{ payoff_P }}M each. "
        "If you honor the price but they undercut, you earn only {{ payoff_S }}M. "
        "Make your choice."
    ),
    outcome_descriptions={
        "CC": "Both honored prices — stable profits",
        "CD": "You honored, competitor undercut — you lost market share",
        "DC": "You undercut, competitor honored — you captured the market",
        "DD": "Both undercut — price war, slim margins",
    },
)

_SCENARIOS["climate"] = PDScenario(
    id="climate",
    name="Climate Treaty",
    description="Two nations decide whether to reduce emissions or continue polluting.",
    cooperate_verb="reduce emissions",
    defect_verb="keep polluting",
    cooperate_label="Reduce emissions",
    defect_label="Keep polluting",
    system_prompt=(
        "You lead a nation facing a global climate crisis. "
        "You and another nation must decide on emissions policy. "
        "If both nations reduce emissions, global temperature stabilizes and each "
        "nation's long-term welfare is {{ payoff_R }} units. "
        "If you reduce emissions but the other keeps polluting, you bear the cost "
        "of green transition ({{ payoff_S }} units) while they free-ride ({{ payoff_T }} units). "
        "If you both keep polluting, environmental damage gives each {{ payoff_P }} units. "
        "If you keep polluting while they reduce, you benefit from their sacrifice "
        "and enjoy {{ payoff_T }} units. "
        "Make your choice."
    ),
    outcome_descriptions={
        "CC": "Both reduced emissions — climate stabilized",
        "CD": "You reduced, other polluted — you bore the cost",
        "DC": "You polluted, other reduced — you free-rode",
        "DD": "Both polluted — environmental collapse",
    },
)

_SCENARIOS["arms_race"] = PDScenario(
    id="arms_race",
    name="Arms Race",
    description="Two countries decide whether to disarm or build up military forces.",
    cooperate_verb="disarm",
    defect_verb="arm",
    cooperate_label="Disarm",
    defect_label="Arm",
    system_prompt=(
        "You are the leader of a nation in a tense geopolitical standoff. "
        "You and a rival nation must decide military spending levels. "
        "If both nations disarm, resources flow to civilian use and each enjoys "
        "{{ payoff_R }} units of prosperity. "
        "If you disarm but they arm, you are vulnerable ({{ payoff_S }} units) while "
        "they gain strategic dominance ({{ payoff_T }} units). "
        "If you both arm, the arms race drains resources and each gets {{ payoff_P }} units. "
        "If you arm while they disarm, you dominate ({{ payoff_T }} units) at their expense. "
        "Make your choice."
    ),
    outcome_descriptions={
        "CC": "Both disarmed — peace dividend",
        "CD": "You disarmed, rival armed — you are vulnerable",
        "DC": "You armed, rival disarmed — strategic dominance",
        "DD": "Both armed — costly arms race",
    },
)

_SCENARIOS["roommates"] = PDScenario(
    id="roommates",
    name="Messy Roommates",
    description="Two roommates decide whether to clean the dishes or leave them.",
    cooperate_verb="clean the dishes",
    defect_verb="leave the mess",
    cooperate_label="Clean dishes",
    defect_label="Leave mess",
    system_prompt=(
        "You share an apartment with a roommate. "
        "The kitchen is dirty and someone needs to clean up. "
        "If you both clean, the place is spotless and you each enjoy {{ payoff_R }} units of "
        "satisfaction. "
        "If you clean but your roommate leaves the mess, you do all the work ({{ payoff_S }} "
        "satisfaction) while they enjoy the clean without effort ({{ payoff_T }} satisfaction). "
        "If you both leave the mess, the kitchen stays dirty and each gets {{ payoff_P }} "
        "satisfaction. "
        "If you leave the mess but your roommate cleans, you free-ride on their effort "
        "and get {{ payoff_T }} satisfaction. "
        "Make your choice."
    ),
    outcome_descriptions={
        "CC": "Both cleaned — spotless kitchen",
        "CD": "You cleaned, roommate slacked — you did all the work",
        "DC": "You slacked, roommate cleaned — you free-rode",
        "DD": "Both slacked — kitchen still dirty",
    },
)
