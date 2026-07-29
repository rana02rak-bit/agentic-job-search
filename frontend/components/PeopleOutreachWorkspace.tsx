"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import {
  api,
  CandidateProfile,
  Company,
  DeliveryCapabilities,
  IntegrationStatus,
  Job,
  OutreachMessage,
  Recruiter,
} from "@/lib/api";

interface PeopleOutreachWorkspaceProps {
  companies: Company[];
  onChanged: () => Promise<void>;
}

async function loadWorkspace() {
  const [people, jobs, messages, capabilities, integrations, profile] =
    await Promise.all([
      api.recruiters(),
      api.allJobs(),
      api.outreachMessages(),
      api.outreachCapabilities(),
      api.integrationStatus(),
      api.profile().catch(() => null),
    ]);
  return { people, jobs, messages, capabilities, integrations, profile };
}

export function PeopleOutreachWorkspace({
  companies,
  onChanged,
}: PeopleOutreachWorkspaceProps) {
  const [people, setPeople] = useState<Recruiter[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [messages, setMessages] = useState<OutreachMessage[]>([]);
  const [capabilities, setCapabilities] = useState<DeliveryCapabilities | null>(null);
  const [integrations, setIntegrations] = useState<IntegrationStatus | null>(null);
  const [profile, setProfile] = useState<CandidateProfile | null>(null);

  const [discoveryCompanyId, setDiscoveryCompanyId] = useState("");
  const [discoveryJobId, setDiscoveryJobId] = useState("");
  const [discoveryLimit, setDiscoveryLimit] = useState("5");

  const [companyId, setCompanyId] = useState("");
  const [personName, setPersonName] = useState("");
  const [linkedinUrl, setLinkedinUrl] = useState("");
  const [designation, setDesignation] = useState("");
  const [activity, setActivity] = useState("");
  const [mutuals, setMutuals] = useState("0");

  const [resumeText, setResumeText] = useState("");
  const [positioning, setPositioning] = useState(
    "AI product, Founder's Office, P2P transformation, consumer internet, and high-ownership roles.",
  );
  const [selectedPersonId, setSelectedPersonId] = useState("");
  const [shortlistJobIds, setShortlistJobIds] = useState<Record<number, string>>({});
  const [selectedPeopleIds, setSelectedPeopleIds] = useState<number[]>([]);
  const [extraContext, setExtraContext] = useState("");
  const [draftSubjects, setDraftSubjects] = useState<Record<number, string>>({});
  const [draftBodies, setDraftBodies] = useState<Record<number, string>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const applyWorkspace = useCallback(
    (data: Awaited<ReturnType<typeof loadWorkspace>>) => {
      setPeople(data.people);
      setJobs(data.jobs);
      setMessages(data.messages);
      setCapabilities(data.capabilities);
      setIntegrations(data.integrations);
      setProfile(data.profile);
      setSelectedPersonId((current) => {
        if (
          current &&
          data.people.some(
            (person) =>
              person.id === Number(current) &&
              person.is_shortlisted &&
              Boolean(person.linkedin_url),
          )
        ) {
          return current;
        }
        const firstShortlisted = data.people.find(
          (person) => person.is_shortlisted && Boolean(person.linkedin_url),
        );
        return firstShortlisted ? String(firstShortlisted.id) : "";
      });
      if (data.profile) {
        setResumeText(data.profile.resume_text);
        setPositioning(data.profile.positioning ?? "");
      }
      setDraftSubjects(
        Object.fromEntries(
          data.messages.map((message) => [message.id, message.subject ?? ""]),
        ),
      );
      setDraftBodies(
        Object.fromEntries(data.messages.map((message) => [message.id, message.body])),
      );
    },
    [],
  );

  const reload = useCallback(async () => {
    applyWorkspace(await loadWorkspace());
  }, [applyWorkspace]);

  useEffect(() => {
    let active = true;
    void loadWorkspace()
      .then((data) => {
        if (active) applyWorkspace(data);
      })
      .catch((caught: unknown) => {
        if (!active) return;
        setError(caught instanceof Error ? caught.message : "Could not load outreach.");
      });
    return () => {
      active = false;
    };
  }, [applyWorkspace]);

  const watchlist = companies.filter((company) => company.is_watchlisted);
  const shortlisted = people.filter(
    (person) => person.is_shortlisted && Boolean(person.linkedin_url),
  );
  const discoveryJobs = jobs.filter(
    (job) => job.company_id === Number(discoveryCompanyId),
  );

  async function runAction(key: string, action: () => Promise<void>) {
    setBusy(key);
    setError(null);
    setNotice(null);
    try {
      await action();
      await reload();
      await onChanged();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The action failed.");
    } finally {
      setBusy(null);
    }
  }

  async function discoverPeople(event: FormEvent) {
    event.preventDefault();
    await runAction("discover-people", async () => {
      const result = await api.discoverRecruiters({
        company_id: Number(discoveryCompanyId),
        job_id: discoveryJobId ? Number(discoveryJobId) : undefined,
        limit: Number(discoveryLimit),
      });
      setNotice(
        result.warning ??
          `ConnectSafely found ${result.discovered}; ${result.stored} new people saved and ${result.skipped_duplicates} duplicates skipped.`,
      );
    });
  }

  async function shortlistSelectedPeople() {
    const peopleToShortlist = people.filter(
      (person) =>
        selectedPeopleIds.includes(person.id) &&
        !person.is_shortlisted &&
        Boolean(person.linkedin_url),
    );
    await runAction("bulk-shortlist", async () => {
      await Promise.all(
        peopleToShortlist.map((person) => api.shortlistRecruiter(person.id)),
      );
      setSelectedPeopleIds([]);
      setNotice(`${peopleToShortlist.length} people shortlisted.`);
    });
  }

  function togglePersonSelection(personId: number) {
    setSelectedPeopleIds((current) =>
      current.includes(personId)
        ? current.filter((id) => id !== personId)
        : [...current, personId],
    );
  }

  async function addPerson() {
    await runAction("add-person", async () => {
      await api.addRecruiter({
        company_id: Number(companyId),
        name: personName.trim(),
        linkedin_url: linkedinUrl.trim(),
        designation: designation.trim() || undefined,
        activity: activity.trim() || undefined,
        mutuals: Number(mutuals) || 0,
      });
      setPersonName("");
      setLinkedinUrl("");
      setDesignation("");
      setActivity("");
      setMutuals("0");
      setNotice("Person added. Shortlist them against a job when ready.");
    });
  }

  async function saveProfile(event: FormEvent) {
    event.preventDefault();
    await runAction("profile", async () => {
      await api.saveProfile({
        name: "Rahul Ranjan",
        resume_text: resumeText,
        positioning: positioning || undefined,
      });
      setNotice("Resume profile saved for AI personalization.");
    });
  }

  async function generateMessage(event: FormEvent) {
    event.preventDefault();
    await runAction("generate", async () => {
      await api.generateOutreach({
        recruiter_id: Number(selectedPersonId),
        extra_context: extraContext.trim() || undefined,
      });
      setExtraContext("");
      setNotice("Your configured AI provider created a unique LinkedIn draft.");
    });
  }

  function subjectFor(message: OutreachMessage) {
    return draftSubjects[message.id] ?? message.subject ?? "";
  }

  function bodyFor(message: OutreachMessage) {
    return draftBodies[message.id] ?? message.body;
  }

  return (
    <section className="workflow" aria-label="People and outreach workflow">
      {(error || notice) && (
        <div className={`workflow-notice ${error ? "workflow-notice--error" : ""}`}>
          {error ?? notice}
        </div>
      )}

      <div className="workflow__heading" id="recruiters">
        <div>
          <p className="eyebrow">People intelligence</p>
          <h2>Discover, shortlist and message the right people.</h2>
        </div>
        <span>{shortlisted.length} shortlisted</span>
      </div>

      <div className="integration-grid">
        <article className="panel connection-card">
          <span className={integrations?.ai_configured ? "status-dot is-ready" : "status-dot"} />
          <div>
            <h3>
              AI drafting · {integrations?.ai_provider?.toUpperCase() ?? "NOT CONFIGURED"}
            </h3>
            <p>
              {integrations?.ai_configured
                ? "Ready for company selection and personal drafts"
                : "Add a fresh Gemini or OpenAI Platform API key"}
            </p>
          </div>
        </article>
        <article className="panel connection-card">
          <span
            className={
              integrations?.connectsafely_account_connected
                ? "status-dot is-ready"
                : "status-dot"
            }
          />
          <div>
            <h3>ConnectSafely + LinkedIn</h3>
            <p>
              {integrations?.connectsafely_account_connected
                ? `Connected as ${integrations.connectsafely_account_name ?? "LinkedIn account"}`
                : integrations?.connectsafely_error
                  ? integrations.connectsafely_error
                : integrations?.connectsafely_configured
                  ? "API key found; connect LinkedIn in ConnectSafely"
                  : "CONNECTSAFELY_API_KEY is missing"}
            </p>
          </div>
        </article>
      </div>
      <p className="helper">
        Secrets are read only by the backend from your local .env file and never entered in this
        browser screen.
      </p>

      <div className="workflow-grid">
        <form className="panel form-stack" onSubmit={discoverPeople}>
          <div className="panel__heading">
            <h3>Auto-find people</h3>
            <span>ConnectSafely search</span>
          </div>
          <label>
            Target company
            <select
              value={discoveryCompanyId}
              onChange={(event) => {
                setDiscoveryCompanyId(event.target.value);
                setDiscoveryJobId("");
              }}
              required
            >
              <option value="">Select company</option>
              {watchlist.map((company) => (
                <option key={company.id} value={company.id}>
                  {company.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Job for auto-shortlist
            <select
              value={discoveryJobId}
              onChange={(event) => setDiscoveryJobId(event.target.value)}
            >
              <option value="">Find only; I will shortlist later</option>
              {discoveryJobs.map((job) => (
                <option key={job.id} value={job.id}>
                  {job.title}
                </option>
              ))}
            </select>
          </label>
          <label>
            People to find
            <select
              value={discoveryLimit}
              onChange={(event) => setDiscoveryLimit(event.target.value)}
            >
              <option value="5">5 people</option>
              <option value="10">10 people</option>
            </select>
          </label>
          <button
            className="button button--primary"
            disabled={
              busy === "discover-people" || !integrations?.ready_for_contact_discovery
            }
          >
            {busy === "discover-people" ? "Searching LinkedIn…" : "Find recruiters and managers"}
          </button>
          {!integrations?.ready_for_contact_discovery && (
            <p className="helper">ConnectSafely and its LinkedIn account must be ready first.</p>
          )}

          <details className="manual-entry">
            <summary>Add a known person manually</summary>
            <div className="form-stack manual-entry__body">
              <label>
                Company
                <select
                  value={companyId}
                  onChange={(event) => setCompanyId(event.target.value)}
                >
                  <option value="">Select company</option>
                  {watchlist.map((company) => (
                    <option key={company.id} value={company.id}>
                      {company.name}
                    </option>
                  ))}
                </select>
              </label>
              <div className="form-pair">
                <label>
                  Name
                  <input
                    value={personName}
                    onChange={(event) => setPersonName(event.target.value)}
                    placeholder="Priya Sharma"
                  />
                </label>
                <label>
                  Designation
                  <input
                    value={designation}
                    onChange={(event) => setDesignation(event.target.value)}
                    placeholder="Talent Partner"
                  />
                </label>
              </div>
              <label>
                LinkedIn profile
                <input
                  type="url"
                  value={linkedinUrl}
                  onChange={(event) => setLinkedinUrl(event.target.value)}
                  placeholder="https://www.linkedin.com/in/…"
                />
              </label>
              <label>
                Recent activity or hiring signal
                <textarea
                  value={activity}
                  onChange={(event) => setActivity(event.target.value)}
                />
              </label>
              <label>
                Mutual connections
                <input
                  type="number"
                  min="0"
                  value={mutuals}
                  onChange={(event) => setMutuals(event.target.value)}
                />
              </label>
              <button
                type="button"
                className="button button--secondary"
                disabled={
                  busy === "add-person" || !companyId || !personName || !linkedinUrl
                }
                onClick={() => void addPerson()}
              >
                Add person
              </button>
            </div>
          </details>
        </form>

        <div className="panel">
          <div className="panel__heading">
            <h3>People queue</h3>
            <span>Bulk selection enabled</span>
          </div>
          <div className="bulk-shortlist-toolbar">
            <p>Select people below, then shortlist them together.</p>
            <button
              type="button"
              className="button button--primary"
              disabled={
                selectedPeopleIds.length === 0 || busy === "bulk-shortlist"
              }
              onClick={() => void shortlistSelectedPeople()}
            >
              {busy === "bulk-shortlist"
                ? "Shortlisting…"
                : `Shortlist selected (${selectedPeopleIds.length})`}
            </button>
          </div>
          <div className="people-list">
            {people.map((person) => {
              const company = companies.find((item) => item.id === person.company_id);
              const companyJobs = jobs.filter((job) => job.company_id === person.company_id);
              return (
                <article className="person-card" key={person.id}>
                  <div>
                    <label className="person-select">
                      <input
                        type="checkbox"
                        checked={
                          person.is_shortlisted ||
                          selectedPeopleIds.includes(person.id)
                        }
                        disabled={person.is_shortlisted}
                        onChange={() => togglePersonSelection(person.id)}
                      />
                      <span>
                        {person.is_shortlisted ? "Already shortlisted" : "Select person"}
                      </span>
                    </label>
                    <p>
                      {company?.name ?? "Company"} · {person.source}
                    </p>
                    <h4>{person.name}</h4>
                    <span>{person.designation ?? "Designation pending"}</span>
                  </div>
                  <strong>{person.reply_probability ?? 0}%</strong>
                  {person.linkedin_url && (
                    <a href={person.linkedin_url} target="_blank" rel="noreferrer">
                      View profile ↗
                    </a>
                  )}
                  {person.is_shortlisted ? (
                    <button
                      type="button"
                      className="button button--secondary"
                      onClick={() =>
                        runAction(`unshortlist-${person.id}`, () =>
                          api.removeRecruiterShortlist(person.id),
                        )
                      }
                    >
                      Shortlisted ✓
                    </button>
                  ) : (
                    <div className="shortlist-control">
                      <label>
                        Optional job
                        <select
                          value={shortlistJobIds[person.id] ?? ""}
                          onChange={(event) =>
                            setShortlistJobIds((current) => ({
                              ...current,
                              [person.id]: event.target.value,
                            }))
                          }
                        >
                          <option value="">No specific job</option>
                          {companyJobs.map((job) => (
                            <option key={job.id} value={job.id}>
                              {job.title}
                            </option>
                          ))}
                        </select>
                      </label>
                      <button
                        type="button"
                        className="button button--primary"
                        disabled={busy === `shortlist-${person.id}`}
                        onClick={() => {
                          const selectedJob = shortlistJobIds[person.id];
                          void runAction(`shortlist-${person.id}`, () =>
                            api
                              .shortlistRecruiter(
                                person.id,
                                selectedJob ? Number(selectedJob) : undefined,
                              )
                              .then(() => undefined),
                          );
                        }}
                      >
                        {busy === `shortlist-${person.id}`
                          ? "Saving…"
                          : "Shortlist person"}
                      </button>
                    </div>
                  )}
                </article>
              );
            })}
            {people.length === 0 && (
              <div className="empty-state">
                <strong>No people stored yet.</strong>
                <p>Select a company and let ConnectSafely search LinkedIn.</p>
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="workflow__heading workflow__heading--spaced" id="outreach">
        <div>
          <p className="eyebrow">Approval-first outreach</p>
          <h2>AI drafts. You approve. ConnectSafely sends.</h2>
        </div>
        <span>
          {capabilities?.sent_today ?? 0}/{capabilities?.daily_limit ?? 100} sent today
        </span>
      </div>

      <div className="workflow-grid workflow-grid--three">
        <form className="panel form-stack" onSubmit={saveProfile}>
          <div className="panel__heading">
            <h3>1. Rahul profile</h3>
            <span>{profile ? "Saved" : "Required"}</span>
          </div>
          <label>
            Resume and strongest evidence
            <textarea
              className="textarea--tall"
              value={resumeText}
              onChange={(event) => setResumeText(event.target.value)}
              placeholder="Paste the updated resume, including Ola Electric, AI agents, ₹30 lakh cost reduction, P2P transformation and Founder's Office work."
              minLength={100}
              required
            />
          </label>
          <label>
            Target positioning
            <textarea
              value={positioning}
              onChange={(event) => setPositioning(event.target.value)}
            />
          </label>
          <button className="button button--dark" disabled={busy === "profile"}>
            Save profile
          </button>
        </form>

        <form className="panel form-stack" onSubmit={generateMessage}>
          <div className="panel__heading">
            <h3>2. Generate DM</h3>
            <span>{integrations?.ai_provider ?? "AI"} · no templates</span>
          </div>
          <label>
            Shortlisted person
            <select
              value={selectedPersonId}
              onChange={(event) => setSelectedPersonId(event.target.value)}
              required
            >
              <option value="">Choose person</option>
              {shortlisted.map((person) => (
                <option key={person.id} value={person.id}>
                  {person.name}
                </option>
              ))}
            </select>
          </label>
          <p className="helper">
            The company and recipient context are selected automatically. No job selection is
            required.
          </p>
          <label>
            Extra context
            <textarea
              value={extraContext}
              onChange={(event) => setExtraContext(event.target.value)}
              placeholder="Recent post, mutual context, or why this role matters"
            />
          </label>
          <button
            className="button button--primary"
            disabled={
              busy === "generate" || !profile || !integrations?.ai_configured
            }
          >
            {busy === "generate" ? "Writing…" : "Generate unique draft"}
          </button>
        </form>

        <div className="panel delivery-panel">
          <div className="panel__heading">
            <h3>3. Delivery controls</h3>
            <span>{capabilities?.mode ?? "CONNECTSAFELY"}</span>
          </div>
          <strong>
            {capabilities?.automatic_linkedin_send
              ? "Approved LinkedIn sending enabled"
              : "LinkedIn delivery is not connected"}
          </strong>
          <p>{capabilities?.reason}</p>
          <div className="limit-meter">
            <span
              style={{
                width: `${Math.min(
                  ((capabilities?.sent_today ?? 0) /
                    (capabilities?.daily_limit ?? 100)) *
                    100,
                  100,
                )}%`,
              }}
            />
          </div>
          <small>Hard local cap: 100 approved sends per day.</small>
        </div>
      </div>

      <div className="message-queue">
        {messages.map((message) => (
          <article className="message-card" key={message.id}>
            <div className="message-card__meta">
              <div>
                <p>
                  {message.job?.company.name ??
                    companies.find(
                      (company) => company.id === message.recruiter.company_id,
                    )?.name ??
                    "Company outreach"}
                </p>
                <h3>
                  {message.recruiter.name}
                  {message.job ? ` · ${message.job.title}` : " · Company conversation"}
                </h3>
              </div>
              <span className={`status-badge status-badge--${message.status.toLowerCase()}`}>
                {message.status}
              </span>
            </div>
            <label>
              InMail subject
              <input
                value={subjectFor(message)}
                onChange={(event) =>
                  setDraftSubjects((current) => ({
                    ...current,
                    [message.id]: event.target.value,
                  }))
                }
                disabled={message.status !== "DRAFT"}
              />
            </label>
            <label>
              Personalized LinkedIn message
              <textarea
                value={bodyFor(message)}
                onChange={(event) =>
                  setDraftBodies((current) => ({
                    ...current,
                    [message.id]: event.target.value,
                  }))
                }
                disabled={message.status !== "DRAFT"}
              />
            </label>
            {message.rationale && <p className="message-rationale">{message.rationale}</p>}
            {message.delivery_error && (
              <p className="workflow-notice workflow-notice--error">{message.delivery_error}</p>
            )}
            <div className="message-actions">
              {message.status === "DRAFT" && (
                <>
                  <button
                    type="button"
                    className="button button--secondary"
                    onClick={() =>
                      runAction(`save-${message.id}`, () =>
                        api
                          .editOutreach(message.id, subjectFor(message), bodyFor(message))
                          .then(() => undefined),
                      )
                    }
                  >
                    Save edit
                  </button>
                  <button
                    type="button"
                    className="button button--primary"
                    onClick={() =>
                      runAction(`approve-${message.id}`, async () => {
                        await api.editOutreach(
                          message.id,
                          subjectFor(message),
                          bodyFor(message),
                        );
                        await api.approveOutreach(message.id);
                        if (capabilities?.automatic_linkedin_send) {
                          await api.autoSendOutreach(message.id);
                          setNotice("DM approved and sent through ConnectSafely.");
                        } else {
                          setNotice(
                            "DM approved but not sent because ConnectSafely is not connected.",
                          );
                        }
                      })
                    }
                  >
                    {capabilities?.automatic_linkedin_send
                      ? "Approve & send LinkedIn DM"
                      : "Approve draft"}
                  </button>
                </>
              )}
              {message.status === "APPROVED" && (
                <button
                  type="button"
                  className="button button--primary"
                  disabled={
                    busy === `send-${message.id}` ||
                    !capabilities?.automatic_linkedin_send
                  }
                  onClick={() =>
                    runAction(`send-${message.id}`, async () => {
                      await api.autoSendOutreach(message.id);
                      setNotice("LinkedIn DM sent through ConnectSafely.");
                    })
                  }
                >
                  {busy === `send-${message.id}`
                    ? "Sending…"
                    : "Retry approved LinkedIn DM"}
                </button>
              )}
              {message.status === "SENDING" && <span>Delivery in progress…</span>}
              {message.status === "SENT" && (
                <button
                  type="button"
                  className="button button--secondary"
                  onClick={() =>
                    runAction(`reply-${message.id}`, () =>
                      api.markOutreachReplied(message.id).then(() => undefined),
                    )
                  }
                >
                  Mark replied
                </button>
              )}
            </div>
          </article>
        ))}
        {messages.length === 0 && (
          <div className="empty-state">
            <strong>No DM drafts yet.</strong>
            <p>Find a person, shortlist them, save your profile, then generate a draft.</p>
          </div>
        )}
      </div>
    </section>
  );
}
