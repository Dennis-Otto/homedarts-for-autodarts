// The editor of own training plans on the training card, for administrators: the plans
// load from the integration, change in rows and chips, and are saved back.
import assert from "node:assert/strict";
import { test } from "node:test";

import { $, $$, DEVICE, loadCards, makeHass, mount, settle, text, window, withLanguage } from "./dom.mjs";

const { editPlans, planProblem, planRows, plansEditorHtml, storedPlans, weekdayNames } = await loadCards();

const ADMIN = { id: "8f1c", name: "Dennis", is_admin: true };
const LIMITS = { plans: 20, steps: 12, name: 40, darts: 1000, rounds: 300 };
const EVENING = {
  name: "Evening",
  steps: [
    { drill: "doubles", darts: 30 },
    { drill: "checkout", rounds: 10, options: { low: 41, high: 100 } },
    { drill: "bobs_27" },
  ],
  weekdays: ["monday", "friday"],
};
const ui = { t: (key) => key };
const DAYS = [
  ["monday", "Mo"],
  ["sunday", "Su"],
];

// Home Assistant's answers to the editor: the plans, then what saving them says.
function connection(...answers) {
  const requests = [];
  const callWS = (message) => {
    requests.push(message);
    return answers.shift()(message);
  };
  return { requests, callWS };
}

const plansAnswer = (plans, limits = LIMITS) => () => Promise.resolve({ plans, limits });

// A board that counted some darts of a training session.
const STATES = { "sensor.training_darts": "24", "switch.training_session": "on" };

function setup({ user = ADMIN, callWS, language = "en" } = {}) {
  const hass = withLanguage(makeHass({ states: STATES, user, callWS }), language);
  return mount("homedarts-training-card", hass);
}

async function opened(card) {
  $(card, ".plans-open").click();
  await settle();
  return $(card, ".plans-dialog");
}

// A change of a field as the browser reports it.
function change(control, value, type) {
  control.value = value;
  control.dispatchEvent(new window.Event(type, { bubbles: true }));
}

const submit = (card) => $(card, ".plans-form").dispatchEvent(new window.Event("submit", { cancelable: true }));

test("the rows of the editor read the plans as the options keep them, and give them back", () => {
  assert.deepEqual(planRows(undefined), []);
  const rows = planRows([EVENING, { name: "Late", steps: [{ drill: "singles", rounds: 5 }] }]);
  assert.deepEqual(rows, [
    {
      name: "Evening",
      weekdays: ["monday", "friday"],
      steps: [
        { drill: "doubles", end: "darts", amount: "30" },
        { drill: "checkout", end: "rounds", amount: "10", options: { low: 41, high: 100 } },
        { drill: "bobs_27", end: "finished", amount: "" },
      ],
    },
    { name: "Late", weekdays: [], steps: [{ drill: "singles", end: "rounds", amount: "5" }] },
  ]);
  assert.deepEqual(storedPlans(rows), [EVENING, { name: "Late", steps: [{ drill: "singles", rounds: 5 }] }]);
  // The finishes of a checkout training go with the game, and a name loses its spaces.
  rows[0].name = " Evening  ";
  rows[0].steps[1].drill = "catch_40";
  assert.deepEqual(storedPlans(rows)[0].steps[1], { drill: "catch_40", rounds: 10 });
  assert.equal(storedPlans(rows)[0].name, "Evening");
});

test("the editor tells a missing name, a name twice and a number that is no limit", () => {
  const rows = () => planRows([EVENING, { name: "Late", steps: [{ drill: "singles", rounds: 5 }] }]);
  assert.equal(planProblem(rows(), LIMITS), null);
  const cases = [
    [(plans) => (plans[1].name = "  "), ["plans_error_name", { number: 2 }]],
    [(plans) => (plans[1].name = " EVENING"), ["plans_error_taken", { name: "EVENING" }]],
    [(plans) => (plans[0].steps[0].amount = ""), ["plans_error_amount", { number: 1, step: 1, max: 1000 }]],
    [(plans) => (plans[0].steps[0].amount = "0"), ["plans_error_amount", { number: 1, step: 1, max: 1000 }]],
    [(plans) => (plans[0].steps[0].amount = "2.5"), ["plans_error_amount", { number: 1, step: 1, max: 1000 }]],
    [(plans) => (plans[1].steps[0].amount = "301"), ["plans_error_amount", { number: 2, step: 1, max: 300 }]],
  ];
  for (const [mistake, problem] of cases) {
    const plans = rows();
    mistake(plans);
    assert.deepEqual(planProblem(plans, LIMITS), problem);
  }
});

test("the editor draws every plan with its name, weekdays and steps", () => {
  const html = plansEditorHtml(planRows([EVENING]), ui, LIMITS, DAYS);
  const root = window.document.createElement("div");
  root.innerHTML = html;
  assert.equal(root.querySelector("legend").textContent, "plans_plan");
  assert.equal(root.querySelector('[data-edit="name"]').value, "Evening");
  assert.deepEqual(
    [...root.querySelectorAll(".day")].map((day) => [day.textContent, day.getAttribute("aria-pressed")]),
    [
      ["Mo", "true"],
      ["Su", "false"],
    ]
  );
  const steps = [...root.querySelectorAll(".plan-step")];
  assert.deepEqual(
    steps.map((step) => [
      step.querySelector(".plan-game option[selected]").value,
      step.querySelector(".plan-end option[selected]").value,
    ]),
    [
      ["doubles", "darts"],
      ["checkout", "rounds"],
      ["bobs_27", "finished"],
    ]
  );
  assert.equal(steps[0].querySelector(".plan-amount").max, "1000");
  assert.equal(steps[1].querySelector(".plan-amount").max, "300");
  // The end of its game ends no step that never ends by itself, and needs no number.
  assert.deepEqual(
    [...steps[1].querySelectorAll(".plan-end option")].map((option) => option.value),
    ["darts", "rounds"]
  );
  assert.equal(steps[2].querySelector(".plan-amount"), null);
  assert.equal(steps[2].querySelectorAll(".plan-end option").length, 3);
  assert.equal(root.querySelector(".step-remove").disabled, false);
  assert.equal(root.querySelector(".plans-add").disabled, false);
  assert.equal(root.querySelector('[data-edit="add-step"]').disabled, false);

  // At the limits, nothing more can be added, and the last step of a plan stays.
  const full = window.document.createElement("div");
  full.innerHTML = plansEditorHtml(
    planRows([{ name: "One", steps: [{ drill: "doubles", darts: 3 }] }]),
    ui,
    { ...LIMITS, plans: 1, steps: 1 },
    DAYS
  );
  assert.equal(full.querySelector(".plans-add").disabled, true);
  assert.equal(full.querySelector('[data-edit="add-step"]').disabled, true);
  assert.equal(full.querySelector(".step-remove").disabled, true);

  const empty = window.document.createElement("div");
  empty.innerHTML = plansEditorHtml([], ui, LIMITS, DAYS);
  assert.equal(empty.querySelector(".plans-none").textContent, "plans_none");
  // Names stay text.
  const hostile = window.document.createElement("div");
  hostile.innerHTML = plansEditorHtml(planRows([{ name: '"><img src=x>', steps: [{ drill: "doubles" }] }]), ui, LIMITS, DAYS);
  assert.equal(hostile.querySelector("img"), null);
  assert.equal(hostile.querySelector('[data-edit="name"]').value, '"><img src=x>');
});

test("the weekdays have their short names in the card's language, from Monday", () => {
  assert.deepEqual(
    weekdayNames(makeHass()).map(([day, name]) => `${day}:${name}`),
    ["monday:Mon", "tuesday:Tue", "wednesday:Wed", "thursday:Thu", "friday:Fri", "saturday:Sat", "sunday:Sun"]
  );
  assert.equal(weekdayNames(withLanguage(makeHass(), "de"))[0][1], "Mo");
});

test("a change in the editor changes the rows, and says which control has the focus then", () => {
  const rows = planRows([EVENING]);
  const control = (dataset, value) => ({ dataset, value });
  assert.equal(editPlans(rows, control({ edit: "name", index: "0" }, "Night")), null);
  assert.equal(editPlans(rows, control({ edit: "amount", index: "0", step: "0" }, "45")), null);
  assert.deepEqual([rows[0].name, rows[0].steps[0].amount], ["Night", "45"]);
  // A game that never ends by itself gets a limit; another keeps the end of its game.
  assert.equal(editPlans(rows, control({ edit: "drill", index: "0", step: "2" }, "singles")), "plans:0:2:drill");
  assert.deepEqual(rows[0].steps[2], { drill: "singles", end: "finished", amount: "" });
  editPlans(rows, control({ edit: "drill", index: "0", step: "2" }, "checkout_121"));
  assert.deepEqual(rows[0].steps[2], { drill: "checkout_121", end: "rounds", amount: "10" });
  editPlans(rows, control({ edit: "drill", index: "0", step: "0" }, "catch_40"));
  assert.deepEqual(rows[0].steps[0], { drill: "catch_40", end: "darts", amount: "45" });
  // A limit keeps its number, a new one starts with one.
  assert.equal(editPlans(rows, control({ edit: "end", index: "0", step: "0" }, "rounds")), "plans:0:0:end");
  assert.equal(rows[0].steps[0].amount, "45");
  editPlans(rows, control({ edit: "end", index: "0", step: "0" }, "finished"));
  assert.equal(rows[0].steps[0].end, "finished");
  rows[0].steps[0].amount = "";
  editPlans(rows, control({ edit: "end", index: "0", step: "0" }, "darts"));
  assert.equal(rows[0].steps[0].amount, "30");
  // The weekdays stay in their order.
  assert.equal(editPlans(rows, control({ edit: "day", index: "0", day: "sunday" })), "plans:0:sunday");
  editPlans(rows, control({ edit: "day", index: "0", day: "monday" }));
  editPlans(rows, control({ edit: "day", index: "0", day: "tuesday" }));
  assert.deepEqual(rows[0].weekdays, ["tuesday", "friday", "sunday"]);
  assert.equal(editPlans(rows, control({ edit: "add-step", index: "0" })), "plans:0:3:drill");
  assert.deepEqual(rows[0].steps[3], { drill: "around_the_clock", end: "darts", amount: "30" });
  assert.equal(editPlans(rows, control({ edit: "remove-step", index: "0", step: "1" })), "plans:0:add-step");
  assert.deepEqual(
    rows[0].steps.map((step) => step.drill),
    ["catch_40", "checkout_121", "around_the_clock"]
  );
  assert.equal(editPlans(rows, control({ edit: "add" })), "plans:1:name");
  assert.deepEqual(rows[1], { name: "", weekdays: [], steps: [{ drill: "around_the_clock", end: "darts", amount: "30" }] });
  assert.equal(editPlans(rows, control({ edit: "remove", index: "0" })), "plans:add");
  assert.equal(rows.length, 1);
});

test("only administrators get the editor of the plans", () => {
  // Without a user too, as before Home Assistant knows who it is.
  for (const user of [{ ...ADMIN, is_admin: false }, null]) {
    const card = setup({ user });
    assert.equal($(card, ".plans-open"), null);
    assert.equal($(card, ".plans-dialog"), null);
  }
  const card = setup();
  assert.equal(text(card, ".plans-open"), "Training plans");
  assert.equal($(card, ".plans-dialog").open, false);
});

test("the editor loads the board's plans, changes them and saves them", async () => {
  const { requests, callWS } = connection(plansAnswer([EVENING]), () => Promise.resolve({ plans: [] }));
  const card = setup({ callWS, language: "de" });
  const dialog = await opened(card);
  assert.equal(dialog.open, true);
  assert.deepEqual(requests, [{ type: "homedarts/plans", device_id: DEVICE }]);
  assert.equal($(card, ".plans-save").disabled, false);
  assert.equal(card.shadowRoot.activeElement, $(card, '[data-edit="name"]'));
  assert.equal(text(card, "#plans-title"), "Trainingspläne");
  assert.equal($(card, ".day").textContent, "Mo");

  // Typing changes the rows only; a choice and a tap draw the plans anew.
  change($(card, '[data-edit="name"]'), "Abend", "input");
  change($(card, ".plan-amount"), "45", "input");
  change($(card, ".plan-game"), "singles", "change");
  assert.equal(card.shadowRoot.activeElement, $(card, ".plan-game"));
  // A select also reports its input, and a text field its change: each counts once,
  // which the plans show once they are drawn anew. (happy-dom keeps the value of the
  // select drawn before, so the option drawn as chosen tells.)
  change($(card, ".plan-game"), "doubles", "input");
  change($(card, '[data-edit="name"]'), "Abend", "change");
  $$(card, ".day")[6].click();
  assert.equal($(card, ".plan-game option[selected]").value, "singles");
  $$(card, ".day")[0].click();
  // A tap beside the controls changes nothing.
  $(card, ".plan-steps").click();
  $$(card, ".step-remove")[2].click();
  assert.equal(card.shadowRoot.activeElement, $(card, '[data-edit="add-step"]'));
  submit(card);
  assert.equal($(card, ".plans-save").disabled, true);
  // A second press while it saves does nothing.
  submit(card);
  await settle();
  assert.deepEqual(requests.slice(1), [
    {
      type: "homedarts/save_plans",
      device_id: DEVICE,
      language: "de",
      plans: [
        {
          name: "Abend",
          steps: [
            { drill: "singles", darts: 45 },
            { drill: "checkout", rounds: 10, options: { low: 41, high: 100 } },
          ],
          weekdays: ["friday", "sunday"],
        },
      ],
    },
  ]);
  assert.equal(dialog.open, false);
  assert.equal(card.shadowRoot.activeElement, $(card, ".plans-open"));
});

test("a mistake stays in the editor with what is wrong, in the words of the card or of the integration", async () => {
  const { requests, callWS } = connection(
    plansAnswer([]),
    () => Promise.reject(new Error("Plan 1 (Abend): the name Abend is taken.")),
    () => Promise.reject(new Error("")),
    () => Promise.resolve({ plans: [] })
  );
  const card = setup({ callWS });
  const dialog = await opened(card);
  assert.equal(text(card, ".plans-none"), "No plans of your own yet.");
  assert.equal(card.shadowRoot.activeElement, $(card, ".plans-add"));
  $(card, ".plans-add").click();
  assert.equal(card.shadowRoot.activeElement, $(card, '[data-edit="name"]'));
  const error = $(card, ".plans-error");
  submit(card);
  assert.equal(error.hidden, false);
  assert.equal(error.textContent, "Plan 1 needs a name.");
  assert.equal(requests.length, 1);

  change($(card, '[data-edit="name"]'), "Abend", "input");
  submit(card);
  await settle();
  assert.equal(error.textContent, "Plan 1 (Abend): the name Abend is taken.");
  assert.equal($(card, ".plans-save").disabled, false);
  assert.equal(dialog.open, true);
  submit(card);
  await settle();
  assert.equal(error.textContent, "The plans could not be saved.");
  submit(card);
  await settle();
  assert.equal(dialog.open, false);
  assert.equal(requests.length, 4);
});

test("a plan can go again, and cancel keeps the plans as they were", async () => {
  const { requests, callWS } = connection(plansAnswer([EVENING]), () => Promise.resolve({ plans: [EVENING] }));
  const card = setup({ callWS });
  const dialog = await opened(card);
  $(card, ".plan-remove").click();
  assert.equal(text(card, ".plans-none"), "No plans of your own yet.");
  assert.equal(card.shadowRoot.activeElement, $(card, ".plans-add"));
  $(card, ".plans-cancel").click();
  assert.equal(dialog.open, false);
  // Opened again, the plans come anew; without limits, those of the card hold.
  await opened(card);
  assert.equal(text(card, "legend"), "Plan 1");
  assert.equal($(card, ".plan-amount").max, "1000");
  assert.equal(requests.length, 2);
});

test("the editor says when the plans cannot be loaded, and waits for nothing once closed", async () => {
  let release;
  const { callWS } = connection(
    () => Promise.reject(new Error("Unauthorized")),
    () => Promise.reject({}),
    () => new Promise((resolve) => (release = resolve))
  );
  const card = setup({ callWS });
  await opened(card);
  assert.equal(text(card, ".plans-error"), "Unauthorized");
  assert.equal($(card, ".plans-save").disabled, true);
  // Saving before the plans are there does nothing.
  submit(card);
  $(card, ".plans-cancel").click();
  await opened(card);
  assert.equal(text(card, ".plans-error"), "The plans could not be saved.");
  $(card, ".plans-cancel").click();

  const dialog = await opened(card);
  assert.equal(text(card, ".plans-body"), "Loading the plans …");
  assert.equal($(card, ".plans-error").hidden, true);
  $(card, ".plans-cancel").click();
  release({ plans: [EVENING], limits: LIMITS });
  await settle();
  assert.equal(dialog.open, false);
  assert.equal($(card, ".plan-edit"), null);
});

test("a preview opens no editor", () => {
  const { requests, callWS } = connection();
  const card = setup({ callWS });
  card.preview = true;
  $(card, ".plans-open").click();
  assert.equal($(card, ".plans-dialog").open, false);
  assert.equal(requests.length, 0);
});
