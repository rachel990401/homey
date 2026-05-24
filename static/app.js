let latestState = null;
let memberPeriods = {};
let snapshotPeriod = "week";
let setupStep = 1;
let setupMode = "create";

async function postJson(url, payload = {}) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return response.json();
}

async function loadState() {
  latestState = await (await fetch("/api/state")).json();
  render(latestState);
}

function render(state) {
  latestState = state;

  applyNavigationState(state);
  renderSetupControls(state);
  renderMemberSummary(state);
  renderExpenseSplit(state);
  renderOverviewCards(state);
  renderChores(state);
  renderBills(state);
  renderSchedule(state);
  renderExpenses(state);
  renderCustomLists(state);

  if (!state.setup_complete) {
    showPage("setup");
  } else if (!isPageEnabled(window.location.hash.replace("#", "") || "overview", state)) {
    showPage("overview");
  }
}

function fillUserSelect(selector, users, includeHousehold = false, placeholder = "Select member") {
  const select = document.querySelector(selector);
  const currentValue = select.value;
  select.innerHTML = `
    <option value="">${placeholder}</option>
    ${includeHousehold ? `<option value="Household">Household</option>` : ""}
    ${users.map((user) => `<option value="${user}">${user}</option>`).join("")}
  `;
  if ([...select.options].some((option) => option.value === currentValue)) {
    select.value = currentValue;
  }
}

function formatDate(dateText) {
  const date = new Date(`${dateText}T00:00:00`);
  if (Number.isNaN(date.getTime())) {
    return dateText || "No date";
  }
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

function renderSetupFields(state, keepExisting = true) {
  const countInput = document.querySelector("#familyCount");
  const container = document.querySelector("#setupNameFields");
  const count = Number(countInput.value);
  if (!Number.isInteger(count) || count < 2 || count > 8) {
    container.innerHTML = "";
    return;
  }
  if (keepExisting && container.children.length === count) {
    return;
  }
  container.innerHTML = "";
  for (let index = 0; index < count; index += 1) {
    const label = document.createElement("label");
    label.innerHTML = `
      Family member ${index + 1}
      <input class="setup-name" type="text" value="${state.users[index] || ""}" placeholder="Member name">
    `;
    container.appendChild(label);
  }
}

function renderSetupControls(state) {
  const amendButton = document.querySelector("#startAmendButton");
  const setupForm = document.querySelector("#setupForm");
  const amendForm = document.querySelector("#amendForm");
  const editing = setupMode === "amend";
  amendButton.hidden = !state.setup_complete || editing;
  amendForm.hidden = !editing;
  setupForm.hidden = editing;
  setupForm.style.display = editing ? "none" : "";
  setupForm.classList.toggle("readonly-setup", state.setup_complete && !editing);
  setSetupFormDisabled(state.setup_complete && !editing);
  setFormError("#amendError", state.form_errors?.setup || "");
  document.querySelector("#setupSubmitButton").textContent = state.setup_complete ? "Save changes" : "Build family dashboard";
  if (editing) {
    renderAmendOptions(state);
  }
  if (state.setup_complete && !editing) {
    populateSetupFromState(state);
  }
  if (!state.setup_complete) {
    renderSetupFields(state);
    showSetupStep(setupStep);
  }
}

function setSetupFormDisabled(disabled) {
  document.querySelectorAll("#setupForm input, #setupForm select, #setupForm button").forEach((item) => {
    item.disabled = disabled;
  });
}

function renderAmendOptions(state) {
  document.querySelector("#deleteMemberName").innerHTML = `
    <option value="">Select member to delete</option>
    ${state.users.map((user) => `<option value="${user}">${user}</option>`).join("")}
  `;
  const sections = [
    ["chores", "Chores / household"],
    ["bills", "Bills / payments"],
    ["schedule", "Schedule"],
    ["expenses", "Paid expenses"],
    ["custom", "Add custom list"],
  ];
  document.querySelector("#sectionAmendName").innerHTML = `
    <option value="">Select section</option>
    ${sections.map(([value, label]) => `<option value="${value}">${label}</option>`).join("")}
  `;
  syncAmendFields();
}

function syncAmendFields() {
  const part = document.querySelector("#amendPart").value;
  const memberAction = document.querySelector("#memberAmendAction").value;
  const sectionAction = document.querySelector("#sectionAmendAction").value;
  document.querySelector("#memberAmendFields").hidden = part !== "members";
  document.querySelector("#sectionAmendFields").hidden = part !== "sections";
  document.querySelector("#newMemberLabel").hidden = part !== "members" || memberAction !== "add";
  document.querySelector("#deleteMemberLabel").hidden = part !== "members" || memberAction !== "delete";
  document.querySelector("#deleteWarningLabel").hidden = part !== "members" || memberAction !== "delete";
  document.querySelector("#sectionAmendName").closest("label").hidden = part !== "sections" || !sectionAction;
  document.querySelector("#amendSubmitButton").hidden = !part || (part === "members" && !memberAction) || (part === "sections" && !sectionAction);
}

function resetAmendForm() {
  document.querySelector("#amendPart").value = "";
  document.querySelector("#memberAmendAction").value = "";
  document.querySelector("#sectionAmendAction").value = "";
  document.querySelector("#sectionAmendName").value = "";
  document.querySelector("#newMemberName").value = "";
  document.querySelector("#confirmDeleteMember").checked = false;
  syncAmendFields();
}

function populateSetupFromState(state) {
  document.querySelector("#familyCount").value = state.users.length || "";
  renderSetupFields(state, false);
  document.querySelectorAll("[name='section']").forEach((input) => {
    input.checked = state.enabled_sections.includes(input.value);
  });
  showSetupStep(1);
}

function selectedSetupSections() {
  return [...document.querySelectorAll("[name='section']:checked")].map((input) => input.value);
}

function setupNames() {
  return [...document.querySelectorAll(".setup-name")].map((input) => input.value.trim());
}

function expenseSelectedInSetup() {
  return selectedSetupSections().includes("expenses");
}

function renderSetupSplitInputs(state) {
  const container = document.querySelector("#setupSplitInputs");
  const names = setupNames();
  container.innerHTML = names.map((name) => `
    <label>
      ${name}
      <input class="setup-split-input" data-setup-split-user="${name}" type="number" min="0" max="100" step="1" value="${state.expense_split?.[name] ?? ""}" placeholder="0">
    </label>
  `).join("");
}

function setupSplitTotal() {
  return [...document.querySelectorAll(".setup-split-input")].reduce((total, input) => total + (Number(input.value) || 0), 0);
}

function selectedSetupSplit() {
  const split = {};
  document.querySelectorAll(".setup-split-input").forEach((input) => {
    split[input.dataset.setupSplitUser] = Number(input.value);
  });
  return split;
}

function ownerOptions(users, currentOwner) {
  return users.map((user) => `<option value="${user}" ${user === currentOwner ? "selected" : ""}>${user}</option>`).join("");
}

function setSetupError(message = "") {
  setFormError("#setupError", message);
}

function setFormError(selector, message = "") {
  const error = document.querySelector(selector);
  error.textContent = message;
  error.classList.toggle("active", Boolean(message));
}

function positiveAmount(value) {
  const amount = Number(value);
  return Number.isFinite(amount) && amount > 0;
}

function validateSetupStep(step) {
  if (step === 1) {
    const countValue = document.querySelector("#familyCount").value.trim();
    const count = Number(countValue);
    if (!countValue || !Number.isInteger(count) || count < 2) {
      setSetupError("Must be at least 2 members.");
      return false;
    }
    if (count > 8) {
      setSetupError("Maximum is 8 members.");
      return false;
    }
  }
  if (step === 2) {
    const names = setupNames();
    const blankName = names.some((name) => !name);
    if (blankName) {
      setSetupError("Enter every family member name.");
      return false;
    }
    const normalizedNames = names.map((name) => name.toLowerCase());
    const hasDuplicate = normalizedNames.some((name, index) => normalizedNames.indexOf(name) !== index);
    if (hasDuplicate) {
      setSetupError("Family member names must be unique.");
      return false;
    }
  }
  if (step === 4 && expenseSelectedInSetup()) {
    if (Math.round(setupSplitTotal() * 100) / 100 !== 100) {
      setSetupError("Split must add up to 100%.");
      return false;
    }
  }
  setSetupError();
  return true;
}

function renderStarterPrompts() {
  const promptCopy = {
    chores: ["Household", "Keep track of chores, pet care, plants, repairs, and who is handling what."],
    bills: ["Bills", "Make payment dates and responsibility visible before someone has to chase."],
    schedule: ["Schedule", "Plan outings, reminders, packing lists, and family availability in one place."],
    expenses: ["Expenses", "Record shared spending so everyone can see who paid and what still needs settling."],
    custom: ["Add-ons", "Create flexible family lists for anything that does not fit the standard pages."],
  };
  const selected = selectedSetupSections();
  const container = document.querySelector("#setupStarterPrompts");
  container.innerHTML = selected.length
    ? selected.map((section) => `
      <article>
        <strong>${promptCopy[section][0]}</strong>
        <span>${promptCopy[section][1]}</span>
      </article>
    `).join("")
    : `<article><strong>Overview only</strong><span>That is okay too. The app will start with member cards only, and you can come back if the family wants more pages.</span></article>`;
}

function showSetupStep(step) {
  setupStep = Math.max(1, Math.min(5, step));
  document.querySelectorAll("[data-setup-step]").forEach((section) => {
    section.classList.toggle("active", Number(section.dataset.setupStep) === setupStep);
  });
  document.querySelectorAll("[data-progress-step]").forEach((item) => {
    const progressStep = Number(item.dataset.progressStep);
    item.classList.toggle("active", progressStep === setupStep);
    item.classList.toggle("done", progressStep < setupStep);
  });
  if (setupStep === 2) {
    renderSetupFields(latestState || { users: [] });
  }
  if (setupStep === 4) {
    renderSetupSplitInputs(latestState || { expense_split: {} });
  }
  if (setupStep === 5) {
    renderStarterPrompts();
  }
}

async function saveSetup() {
  if (!validateSetupStep(1)) {
    showSetupStep(1);
    return;
  }
  if (!validateSetupStep(2)) {
    showSetupStep(2);
    return;
  }
  if (expenseSelectedInSetup() && !validateSetupStep(4)) {
    showSetupStep(4);
    return;
  }
  const names = setupNames();
  const sections = selectedSetupSections();
  const split = expenseSelectedInSetup() ? selectedSetupSplit() : {};
  setupMode = "create";
  render(await postJson("/api/setup", { names, sections, split }));
  showPage("overview");
}

function renderMemberSummary(state) {
  const hasSection = (section) => state.enabled_sections.includes(section);
  document.querySelector("#memberSummary").innerHTML = state.users.map((user) => {
    const period = memberPeriods[user] || "week";
    const member = (state.member_summaries[period] || []).find((item) => item.user === user) || { user };
    return `
    <article class="member-card">
      <div class="member-header">
        <div>
          <span>Member</span>
          <strong>${member.user}</strong>
        </div>
        <select class="period-select member-period-select" data-member-period="${member.user}">
          ${periodOptions(period)}
        </select>
        ${hasSection("expenses") ? `<b>$${member.expenses_paid.toFixed(2)}</b>` : ""}
      </div>
      ${hasSection("chores") ? renderMemberChoreBlock(member, period) : ""}
      ${hasSection("bills") ? renderMemberBillBlock(member, period) : ""}
      ${hasSection("schedule") ? renderMemberScheduleBlock(member, period) : ""}
      ${hasSection("expenses") ? `<div class="summary-section"><h3>Expenses</h3><div class="summary-row"><span>Paid</span><strong>$${member.expenses_paid.toFixed(2)}</strong></div></div>` : ""}
    </article>
  `;
  }).join("");

  document.querySelectorAll("[data-alert-page]").forEach((button) => {
    button.addEventListener("click", () => showPage(button.dataset.alertPage));
  });
  document.querySelectorAll("[data-member-period]").forEach((select) => {
    select.addEventListener("change", () => {
      memberPeriods[select.dataset.memberPeriod] = select.value;
      renderMemberSummary(latestState);
    });
  });
}

function periodOptions(selected) {
  const options = [
    ["all", "Overall"],
    ["day", "Today"],
    ["tomorrow", "Tomorrow"],
    ["week", "This week"],
    ["next_week", "Next week"],
    ["month", "This month"],
    ["next_month", "Next month"],
  ];
  return options.map(([value, label]) => `<option value="${value}" ${value === selected ? "selected" : ""}>${label}</option>`).join("");
}

function renderMetricGrid(items) {
  return `<div class="metric-grid">${items.map((item) => `
    <div><span>${item.label}</span><strong>${item.value}</strong></div>
  `).join("")}</div>`;
}

function renderAlertList(items, type, page) {
  if (!items.length) {
    return "";
  }
  return `<div class="alert-list">${items.slice(0, 3).map((item) => `
    <button class="alert-pill ${type}" data-alert-page="${page}" type="button">
      <b>${item.title}</b>
      <span>${item.detail}</span>
    </button>
  `).join("")}</div>`;
}

function periodLabel(period) {
  return {
    all: "Pending",
    day: "Today",
    tomorrow: "Tomorrow",
    week: "This week",
    next_week: "Next week",
    month: "This month",
    next_month: "Next month",
  }[period] || "Pending";
}

function reminderPrefix(page, period) {
  if (page === "bills") {
    return "Pending";
  }
  return periodLabel(period);
}

function renderPendingOverview(items, page, period, type = "danger") {
  if (!items.length) {
    return `<p class="none-pending">None pending</p>`;
  }
  const rows = items.map((item) => ({
    title: page === "bills"
      ? `Pending Payment: ${item.title.replace(/^Payment: /, "")}`
      : `${reminderPrefix(page, period)}: ${item.title}`,
    detail: item.detail,
  }));
  return renderAlertList(rows, type, page);
}

function renderUpcomingSchedule(items) {
  if (!items.length) {
    return `<p class="none-pending">None pending</p>`;
  }
  const rows = items.map((item) => ({
    title: `Upcoming: ${item.title}`,
    detail: item.detail,
  }));
  return renderAlertList(rows, "warning", "schedule");
}

function renderMemberChoreBlock(member, period) {
  const summary = member.chore_summary || { pending_alerts: [] };
  return `
    <div class="summary-section">
      <h3>Chores</h3>
      ${renderPendingOverview(summary.pending_alerts || [], "chores", period)}
    </div>
  `;
}

function renderMemberBillBlock(member, period) {
  const summary = member.bill_member_summary || { pending_alerts: [] };
  return `
    <div class="summary-section">
      <h3>Bills</h3>
      ${renderPendingOverview(summary.pending_alerts || [], "bills", period)}
    </div>
  `;
}

function renderMemberScheduleBlock(member, period) {
  const summary = member.schedule_summary || { pending_compulsory: [], pending_optional: [], upcoming_items: [] };
  const hasResponses = summary.pending_compulsory.length || summary.pending_optional.length;
  return `
    <div class="summary-section">
      <h3>Schedule</h3>
      ${renderAlertList(summary.pending_compulsory, "danger", "schedule")}
      ${renderAlertList(summary.pending_optional, "warning", "schedule")}
      ${hasResponses ? "" : renderUpcomingSchedule(summary.upcoming_items || [])}
    </div>
  `;
}

function splitTotal() {
  return [...document.querySelectorAll(".split-input")].reduce((total, input) => total + (Number(input.value) || 0), 0);
}

function renderExpenseSplit(state) {
  const panel = document.querySelector("#expenseSplitPanel");
  panel.hidden = !isPageEnabled("expenses", state);
  if (panel.hidden) {
    return;
  }
  document.querySelector("#splitInputs").innerHTML = state.users.map((user) => `
    <label>
      ${user}
      <input class="split-input" data-split-user="${user}" type="number" min="0" max="100" step="1" value="${state.expense_split[user] ?? 0}">
    </label>
  `).join("");
  document.querySelector("#splitTotalHint").textContent = `Total: ${splitTotal()}%`;
}

function renderOverviewCards(state) {
  const snapshot = state.household_snapshots?.[snapshotPeriod] || {};
  const schedulePending = snapshot.schedule?.pending ?? 0;
  const scheduleScheduled = snapshot.schedule?.scheduled ?? 0;
  const cards = [
    { page: "chores", label: "Household", value: `${snapshot.chores?.pending ?? 0} pending`, detail: `Due: ${snapshot.chores?.due || "None"}` },
    { page: "bills", label: "Bills", value: `${snapshot.bills?.pending ?? 0} pending`, detail: `Due: ${snapshot.bills?.due || "None"}` },
    {
      page: "schedule",
      label: "Schedule",
      value: schedulePending ? `${schedulePending} pending response` : `${scheduleScheduled} scheduled`,
      detail: `${schedulePending ? "Next pending" : "Next"}: ${snapshot.schedule?.due || "None"}`,
    },
    { page: "expenses", label: "Paid Expenses", value: snapshot.expenses?.paid || "$0.00", detail: `${snapshot.expenses?.count ?? 0} paid records` },
    { page: "custom", label: "Add-ons", value: `${snapshot.custom?.pending ?? 0} lists`, detail: snapshot.custom?.due || "Custom lists" },
  ].filter((card) => isPageEnabled(card.page, state));

  document.querySelector("#overviewCards").innerHTML = cards.map((card) => `
    <button class="overview-card" data-overview-page="${card.page}">
      <span>${card.label}</span>
      <strong>${card.value}</strong>
      <small>${card.detail}</small>
    </button>
  `).join("") || `<article class="overview-card empty-overview">
    <span>Overview only for now</span>
    <strong>Overview only</strong>
    <small>No problem. Add pages later if the family wants chores, bills, schedule, expenses, or add-ons.</small>
  </article>`;

  document.querySelectorAll("[data-overview-page]").forEach((button) => {
    button.addEventListener("click", () => showPage(button.dataset.overviewPage));
  });
}

function renderChores(state) {
  fillUserSelect("#choreAssignee", state.users, false, "Select who is pending");
  setFormError("#choreError", state.form_errors?.chore || "");
  document.querySelector("#choreBoard").innerHTML = state.chores_by_category.length
    ? state.chores_by_category.map((category) => `
    <article class="board-card">
      <div class="shared-title">
        <div>
          <strong>${category.name}</strong>
          <span>${category.chores.filter((chore) => !chore.done).length} pending</span>
        </div>
      </div>
      <div class="compact-list">
        ${category.chores.map((chore) => `
          <div class="compact-item ${chore.done ? "done" : ""}">
            <div>
              <b>${chore.title}</b>
              <span>${chore.frequency} · ${chore.assigned_to} · ${formatDate(chore.due_date)}</span>
            </div>
            <div class="item-actions">
              <select data-chore-owner="${chore.id}" ${chore.done ? "disabled" : ""}>${ownerOptions(state.users, chore.assigned_to)}</select>
              <button class="ghost" data-switch-chore="${chore.id}" ${chore.done ? "disabled" : ""}>Switch</button>
              <button data-complete="${chore.id}" ${chore.done ? "disabled" : ""}>${chore.done ? "Done" : "Complete"}</button>
            </div>
          </div>
        `).join("")}
      </div>
    </article>
  `).join("")
    : `<article class="board-card"><strong>Nothing to chase yet.</strong><p class="empty-note">When the family is ready, add something like Laundry, Dog dinner, Plant watering, or a repair task.</p></article>`;

  document.querySelectorAll("[data-complete]").forEach((button) => {
    button.addEventListener("click", async () => {
      render(await postJson(`/api/chores/${button.dataset.complete}/complete`));
    });
  });
  document.querySelectorAll("[data-switch-chore]").forEach((button) => {
    button.addEventListener("click", async () => {
      const owner = document.querySelector(`[data-chore-owner="${button.dataset.switchChore}"]`).value;
      render(await postJson(`/api/chores/${button.dataset.switchChore}/switch-owner`, { assigned_to: owner }));
    });
  });
}

function renderBills(state) {
  fillUserSelect("#billPendingWho", state.users, false, "Select who pays");
  setFormError("#billError", state.form_errors?.bill || "");
  document.querySelector("#billSummary").textContent =
    `$${state.bill_summary.unpaid_total.toFixed(2)} unpaid · ${state.bill_summary.unpaid_count} pending`;
  document.querySelector("#billList").innerHTML = state.bills.length ? state.bills.map((bill) => `
    <article class="compact-item ${bill.paid ? "done" : ""}">
      <div>
        <b>${bill.title}</b>
        <span>${bill.category} · $${bill.amount.toFixed(2)} · due ${formatDate(bill.due_date)} · ${bill.pending_who}</span>
      </div>
      <div class="item-actions">
        <select data-bill-owner="${bill.id}" ${bill.paid ? "disabled" : ""}>${ownerOptions(state.users, bill.pending_who)}</select>
        <button class="ghost" data-switch-bill="${bill.id}" ${bill.paid ? "disabled" : ""}>Switch</button>
        <button data-bill-status="${bill.id}" data-bill-paid="${bill.paid}">${bill.paid ? "Mark unpaid" : "Mark paid"}</button>
      </div>
    </article>
  `).join("") : `<article class="compact-item"><div><b>No bills added yet.</b><span>Add rent, electricity, internet, water, or school fees when you want them tracked.</span></div></article>`;

  document.querySelectorAll("[data-bill-status]").forEach((button) => {
    button.addEventListener("click", async () => {
      const action = button.dataset.billPaid === "true" ? "unpay" : "pay";
      render(await postJson(`/api/bills/${button.dataset.billStatus}/${action}`));
    });
  });
  document.querySelectorAll("[data-switch-bill]").forEach((button) => {
    button.addEventListener("click", async () => {
      const owner = document.querySelector(`[data-bill-owner="${button.dataset.switchBill}"]`).value;
      render(await postJson(`/api/bills/${button.dataset.switchBill}/switch-owner`, { pending_who: owner }));
    });
  });
}

function renderSchedule(state) {
  fillUserSelect("#scheduleOwner", state.users, false, "Select owner");
  setFormError("#scheduleError", state.form_errors?.schedule || "");
  syncScheduleDateFields();
  renderScheduleAttendees(state);
  const acceptedItems = state.scheduled_items.filter((item) => item.confirmed);
  document.querySelector("#scheduleCalendar").innerHTML = renderMonthCalendar(state.schedule_calendar, acceptedItems);
  document.querySelector("#scheduleList").innerHTML = state.scheduled_items.length ? state.scheduled_items.map((item) => `
    <article class="planner-item ${item.compulsory_declined.length ? "needs-reschedule" : ""}">
      <div class="date-tile">
        <span>${formatDate(item.date).split(" ")[0]}</span>
        <strong>${formatDate(item.date).split(" ")[1]?.replace(",", "") || ""}</strong>
      </div>
      <div>
        <div class="shared-title">
          <div>
            <strong>${item.title}</strong>
            <span>${item.owner} · ${item.date_label || formatDate(item.date)}</span>
          </div>
        </div>
        <p>${item.note}</p>
        <p class="${item.compulsory_declined.length ? "reschedule-warning-text" : "empty-note"}">${item.status_text}</p>
        <div class="response-grid">
          ${Object.entries(item.responses).map(([user, response]) => renderScheduleResponse(item, user, response)).join("")}
        </div>
        ${item.compulsory_declined.length ? renderRescheduleBox(item) : ""}
      </div>
    </article>
  `).join("") : `<article class="planner-item"><div class="date-tile"><span>--</span><strong>--</strong></div><div><strong>The calendar is quiet.</strong><p class="empty-note">Add something like holiday packing, Saturday badminton, or a family dinner plan.</p></div></article>`;

  document.querySelectorAll("[data-schedule-response]").forEach((button) => {
    button.addEventListener("click", async () => {
      render(await postJson(`/api/schedule/${button.dataset.scheduleResponse}/response`, {
        user: button.dataset.scheduleUser,
        response: button.dataset.response,
      }));
    });
  });
  document.querySelectorAll("[data-reschedule]").forEach((button) => {
    button.addEventListener("click", async () => {
      const id = button.dataset.reschedule;
      const duration = Number(button.dataset.rescheduleDuration || 1);
      const payload = duration > 1
        ? {
            start_date: document.querySelector(`[data-reschedule-start="${id}"]`).value,
            end_date: document.querySelector(`[data-reschedule-end="${id}"]`).value,
          }
        : {
            date: document.querySelector(`[data-reschedule-date="${id}"]`).value,
          };
      if ((duration > 1 && (!payload.start_date || !payload.end_date)) || (duration <= 1 && !payload.date)) {
        return;
      }
      render(await postJson(`/api/schedule/${id}/reschedule`, payload));
      showPage("overview");
    });
  });
}

function renderRescheduleBox(item) {
  const isMultiDay = Number(item.duration_days || 1) > 1;
  return `
    <div class="reschedule-box">
      <strong>Reschedule required</strong>
      <span>${item.compulsory_declined.join(", ")} cannot make it. Choose ${isMultiDay ? "a new start and end date" : "a new date"} and everyone will respond again.</span>
      <div class="reschedule-row ${isMultiDay ? "multi-day" : ""}">
        ${isMultiDay
          ? `
            <label>Start date <input type="date" data-reschedule-start="${item.id}"></label>
            <label>End date <input type="date" data-reschedule-end="${item.id}"></label>
          `
          : `<label>New date <input type="date" data-reschedule-date="${item.id}"></label>`}
        <button data-reschedule="${item.id}" data-reschedule-duration="${item.duration_days || 1}">Reschedule</button>
      </div>
    </div>
  `;
}

function renderMonthCalendar(calendar, acceptedItems) {
  if (!calendar) {
    return `<article class="calendar-shell"><b>Calendar</b><span>Accepted events will appear here.</span></article>`;
  }
  return `
    <section class="calendar-shell">
      <div class="calendar-header">
        <div>
          <span>Monthly Calendar</span>
          <strong>${calendar.month_label}</strong>
        </div>
        <small>${acceptedItems.length} confirmed</small>
      </div>
      <div class="month-grid">
        ${calendar.weekdays.map((day) => `<b>${day}</b>`).join("")}
        ${calendar.weeks.flat().map((day) => `
          <div class="month-cell ${day.in_month ? "" : "muted"} ${day.today ? "today" : ""} ${day.events.length ? "has-event" : ""}">
            <span>${day.day}</span>
            ${day.events.slice(0, 2).map((item) => `<em>${item.title}</em>`).join("")}
          </div>
        `).join("")}
      </div>
    </section>
    <section class="confirmed-events">
      <div class="calendar-header">
        <div>
          <span>Confirmed Events</span>
          <strong>Scheduled successfully</strong>
        </div>
      </div>
      ${acceptedItems.length ? acceptedItems.map((item) => `
        <article class="confirmed-event-card">
          <div class="date-tile compact-date">
            <span>${formatDate(item.date).split(" ")[0]}</span>
            <strong>${formatDate(item.date).split(" ")[1]?.replace(",", "") || ""}</strong>
          </div>
          <div>
            <b>${item.title}</b>
            <span>${item.owner} · ${item.date_label || formatDate(item.date)}</span>
          </div>
        </article>
      `).join("") : `<p class="empty-note">Accepted events will appear here after compulsory members approve.</p>`}
    </section>
  `;
}

function renderScheduleAttendees(state) {
  const owner = document.querySelector("#scheduleOwner").value;
  const container = document.querySelector("#scheduleAttendees");
  if (!owner) {
    container.innerHTML = `<span class="field-caption muted-caption">Select owner first</span>`;
    return;
  }
  const otherMembers = state.users.filter((user) => user !== owner);
  container.innerHTML = otherMembers.length ? `
    <span class="field-caption">Invite members</span>
    ${otherMembers.map((user) => `
      <label>
        ${user}
        <select class="attendee-role" data-attendee-user="${user}">
          <option value="">Select compulsory or optional</option>
          <option value="Compulsory">Compulsory</option>
          <option value="Optional">Optional</option>
        </select>
      </label>
    `).join("")}
  ` : "";
}

function selectedAttendance() {
  const attendance = {};
  document.querySelectorAll(".attendee-role").forEach((select) => {
    attendance[select.dataset.attendeeUser] = select.value;
  });
  return attendance;
}

function syncScheduleDateFields() {
  const rawDuration = document.querySelector("#scheduleDuration").value.trim();
  const duration = Number(rawDuration);
  const hasDuration = rawDuration !== "" && Number.isFinite(duration) && duration >= 1;
  const multiDay = hasDuration && duration > 1;
  document.querySelector("#scheduleSingleDateLabel").hidden = !hasDuration || multiDay;
  document.querySelector("#scheduleStartDateLabel").hidden = !multiDay;
  document.querySelector("#scheduleEndDateLabel").hidden = !multiDay;
}

function renderScheduleResponse(item, user, response) {
  const role = item.attendance?.[user] || (user === item.owner ? "Creator" : "Compulsory");
  if (user === item.owner) {
    return `
      <div class="response-row">
        <span>${user}: Creator</span>
      </div>
    `;
  }
  return `
    <div class="response-row">
      <span>${user}: ${response} · ${role}</span>
      <div class="response-actions">
        <button class="ghost" data-schedule-response="${item.id}" data-schedule-user="${user}" data-response="Accepted">Accept</button>
        <button class="ghost" data-schedule-response="${item.id}" data-schedule-user="${user}" data-response="Declined">Reject</button>
      </div>
    </div>
  `;
}

function renderExpenses(state) {
  fillUserSelect("#expensePaidBy", state.users, false, "Select who paid");
  fillUserSelect("#expenseForMember", state.users, true, "Select who it is for");
  setFormError("#expenseError", state.form_errors?.expense || "");
  document.querySelector("#expenseTotal").textContent = `$${state.expense_summary.total.toFixed(2)} total`;
  document.querySelector("#expenseBalances").innerHTML = state.expense_summary.balances.map((balance) => `
    <article class="balance-card paid-card ${balance.paid > 0 ? "has-paid" : "is-clear"}">
      <span>${balance.user}</span>
      <strong>${balance.paid > 0 ? "-" : ""}$${balance.paid.toFixed(2)}</strong>
      <small>Paid out $${balance.paid.toFixed(2)} · ${balance.split_percent}% share $${balance.fair_share.toFixed(2)}</small>
    </article>
  `).join("");
  document.querySelector("#expenseReconciliation").innerHTML = renderReconciliation(state.expense_summary.settlements);
  document.querySelector("#expenseList").innerHTML = state.expenses.length ? state.expenses.map((expense) => `
    <article class="compact-item">
      <div>
        <b>${expense.title}</b>
        <span>${expense.category} · $${expense.amount.toFixed(2)} · paid by ${expense.paid_by} · ${formatDate(expense.date)}</span>
      </div>
    </article>
  `).join("") : `<article class="compact-item"><div><b>No shared spending yet.</b><span>Add groceries, pet food, school items, or anything someone paid for the household.</span></div></article>`;
}

function renderReconciliation(settlements = []) {
  return `
    <div class="reconciliation-title">
      <strong>Reconciliation</strong>
      <span>Only shows who owes who</span>
    </div>
    ${settlements.length
      ? settlements.map((item) => `
        <div class="reconciliation-row">
          <span>${item.from} owes ${item.to}</span>
          <strong>$${item.amount.toFixed(2)}</strong>
        </div>
      `).join("")
      : `<p class="none-pending">Everyone is settled.</p>`}
  `;
}

function renderCustomLists(state) {
  fillUserSelect("#customOwner", state.users, false, "Select owner");
  setFormError("#customError", state.form_errors?.custom || "");
  document.querySelector("#customList").innerHTML = state.custom_lists.length ? state.custom_lists.map((item) => `
    <article class="custom-card accent-blue">
      <div class="shared-title">
        <div>
          <strong>${item.title}</strong>
          <span>${item.owner}</span>
        </div>
        <em class="custom-label label-blue size-medium">${item.label}</em>
      </div>
      <p>${item.detail}</p>
    </article>
  `).join("") : `<article class="custom-card accent-blue"><strong>No extra lists yet.</strong><p class="empty-note">Create a packing list, exam week plan, guest prep list, or anything your family keeps forgetting.</p></article>`;
}

function isPageEnabled(pageName, state = latestState) {
  if (pageName === "setup") {
    return true;
  }
  if (pageName === "overview") {
    return Boolean(state?.setup_complete);
  }
  return Boolean(state?.setup_complete && state.enabled_sections.includes(pageName));
}

function applyNavigationState(state) {
  document.querySelectorAll("[data-page-target]").forEach((button) => {
    button.hidden = !isPageEnabled(button.dataset.pageTarget, state);
  });
  document.querySelectorAll("[data-page]").forEach((page) => {
    page.hidden = !isPageEnabled(page.dataset.page, state);
  });
}

function showPage(pageName) {
  const fallback = latestState?.setup_complete ? "overview" : "setup";
  const targetName = document.querySelector(`[data-page="${pageName}"]`) && isPageEnabled(pageName) ? pageName : fallback;
  document.querySelectorAll("[data-page]").forEach((page) => {
    page.classList.toggle("active", page.dataset.page === targetName);
  });
  document.querySelectorAll("[data-page-target]").forEach((button) => {
    button.classList.toggle("active", button.dataset.pageTarget === targetName);
  });
  window.location.hash = targetName;
  window.scrollTo({ top: 0, behavior: "smooth" });
}

document.querySelector("#familyCount").addEventListener("input", () => {
  setSetupError();
  renderSetupFields(latestState || { users: [] });
});

document.querySelector("#startAmendButton").addEventListener("click", () => {
  setupMode = "amend";
  resetAmendForm();
  renderSetupControls(latestState);
});

document.querySelector("#cancelAmendButton").addEventListener("click", () => {
  setupMode = "create";
  renderSetupControls(latestState);
});

document.querySelector("#amendPart").addEventListener("change", syncAmendFields);
document.querySelector("#memberAmendAction").addEventListener("change", syncAmendFields);
document.querySelector("#sectionAmendAction").addEventListener("change", syncAmendFields);

document.querySelector("#amendForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const part = document.querySelector("#amendPart").value;
  const payload = { part };
  if (part === "members") {
    payload.action = document.querySelector("#memberAmendAction").value;
    payload.name = payload.action === "add" ? document.querySelector("#newMemberName").value : document.querySelector("#deleteMemberName").value;
    payload.confirmed = document.querySelector("#confirmDeleteMember").checked;
  }
  if (part === "sections") {
    payload.action = document.querySelector("#sectionAmendAction").value;
    payload.section = document.querySelector("#sectionAmendName").value;
  }
  const state = await postJson("/api/setup/amend", payload);
  render(state);
  if (!state.form_errors?.setup) {
    resetAmendForm();
  }
});

document.querySelectorAll("[data-setup-next]").forEach((button) => {
  button.addEventListener("click", () => {
    if (validateSetupStep(setupStep)) {
      showSetupStep(setupStep === 3 && !expenseSelectedInSetup() ? 5 : setupStep + 1);
    }
  });
});

document.querySelectorAll("[data-setup-back]").forEach((button) => {
  button.addEventListener("click", () => {
    setSetupError();
    showSetupStep(setupStep === 5 && !expenseSelectedInSetup() ? 3 : setupStep - 1);
  });
});

document.querySelectorAll("[name='section']").forEach((input) => {
  input.addEventListener("change", renderStarterPrompts);
});

document.querySelector("#setupForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (setupStep < 5) {
    if (validateSetupStep(setupStep)) {
      showSetupStep(setupStep === 3 && !expenseSelectedInSetup() ? 5 : setupStep + 1);
    }
    return;
  }
  saveSetup();
});

document.querySelector("#snapshotPeriod").addEventListener("change", (event) => {
  snapshotPeriod = event.target.value;
  renderOverviewCards(latestState);
});

document.querySelector("#splitForm").addEventListener("input", () => {
  document.querySelector("#splitTotalHint").textContent = `Total: ${splitTotal()}%`;
  setFormError("#splitError");
});

document.querySelector("#splitForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const total = splitTotal();
  if (Math.round(total * 100) / 100 !== 100) {
    setFormError("#splitError", "Split must add up to 100%.");
    return;
  }
  const split = {};
  document.querySelectorAll(".split-input").forEach((input) => {
    split[input.dataset.splitUser] = Number(input.value);
  });
  setFormError("#splitError");
  render(await postJson("/api/expense-split", { split }));
});

document.querySelector("#exportSummaryButton").addEventListener("click", async () => {
  const state = await postJson("/api/export-summary");
  render(state);
  const fileName = state.export_file ? state.export_file.split("/").pop() : "Export failed";
  document.querySelector("#exportHint").textContent = fileName;
});

document.querySelector("#choreForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  setFormError("#choreError");
  const state = await postJson("/api/chores", {
    category: document.querySelector("#choreCategory").value,
    title: document.querySelector("#choreTitle").value,
    frequency: document.querySelector("#choreFrequency").value,
    due_date: document.querySelector("#choreDueDate").value,
    assigned_to: document.querySelector("#choreAssignee").value,
  });
  render(state);
  if (!state.form_errors?.chore) {
    document.querySelector("#choreCategory").value = "";
    document.querySelector("#choreTitle").value = "";
    document.querySelector("#choreFrequency").value = "";
    document.querySelector("#choreDueDate").value = "";
    document.querySelector("#choreAssignee").value = "";
  }
});

document.querySelector("#billForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  setFormError("#billError");
  const state = await postJson("/api/bills", {
    category: document.querySelector("#billCategory").value,
    title: document.querySelector("#billTitle").value,
    amount: document.querySelector("#billAmount").value,
    due_date: document.querySelector("#billDueDate").value,
    pending_who: document.querySelector("#billPendingWho").value,
  });
  render(state);
  if (!state.form_errors?.bill) {
    document.querySelector("#billCategory").value = "";
    document.querySelector("#billTitle").value = "";
    document.querySelector("#billAmount").value = "";
    document.querySelector("#billDueDate").value = "";
    document.querySelector("#billPendingWho").value = "";
  }
});

document.querySelector("#scheduleOwner").addEventListener("change", () => {
  renderScheduleAttendees(latestState || { users: [] });
});

document.querySelector("#scheduleDuration").addEventListener("input", syncScheduleDateFields);

document.querySelector("#scheduleForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const duration = document.querySelector("#scheduleDuration").value;
  setFormError("#scheduleError");
  const state = await postJson("/api/schedule", {
    title: document.querySelector("#scheduleTitle").value,
    date: document.querySelector("#scheduleDate").value,
    start_date: document.querySelector("#scheduleStartDate").value,
    end_date: document.querySelector("#scheduleEndDate").value,
    duration_days: duration,
    owner: document.querySelector("#scheduleOwner").value,
    attendance: selectedAttendance(),
    note: document.querySelector("#scheduleNote").value,
  });
  render(state);
  if (!state.form_errors?.schedule) {
    document.querySelector("#scheduleTitle").value = "";
    document.querySelector("#scheduleDuration").value = "";
    document.querySelector("#scheduleDate").value = "";
    document.querySelector("#scheduleStartDate").value = "";
    document.querySelector("#scheduleEndDate").value = "";
    document.querySelector("#scheduleOwner").value = "";
    document.querySelector("#scheduleNote").value = "";
    renderScheduleAttendees(state);
  }
});

document.querySelector("#expenseForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  setFormError("#expenseError");
  const state = await postJson("/api/expenses", {
    title: document.querySelector("#expenseTitle").value,
    category: document.querySelector("#expenseCategory").value,
    amount: document.querySelector("#expenseAmount").value,
    date: document.querySelector("#expenseDate").value,
    paid_by: document.querySelector("#expensePaidBy").value,
    for_member: document.querySelector("#expenseForMember").value,
  });
  render(state);
  if (!state.form_errors?.expense) {
    document.querySelector("#expenseTitle").value = "";
    document.querySelector("#expenseCategory").value = "";
    document.querySelector("#expenseAmount").value = "";
    document.querySelector("#expenseDate").value = "";
    document.querySelector("#expensePaidBy").value = "";
    document.querySelector("#expenseForMember").value = "";
  }
});

document.querySelector("#customForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  setFormError("#customError");
  const state = await postJson("/api/custom-lists", {
    title: document.querySelector("#customTitle").value,
    owner: document.querySelector("#customOwner").value,
    label: document.querySelector("#customLabel").value,
    detail: document.querySelector("#customDetail").value,
  });
  render(state);
  if (!state.form_errors?.custom) {
    document.querySelector("#customTitle").value = "";
    document.querySelector("#customOwner").value = "";
    document.querySelector("#customLabel").value = "";
    document.querySelector("#customDetail").value = "";
  }
});

document.querySelectorAll("[data-page-target]").forEach((button) => {
  button.addEventListener("click", () => showPage(button.dataset.pageTarget));
});

window.addEventListener("hashchange", () => {
  showPage(window.location.hash.replace("#", "") || "overview");
});

showPage(window.location.hash.replace("#", "") || "setup");
loadState();
