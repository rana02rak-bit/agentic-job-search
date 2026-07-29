"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import {
  api,
  CandidateProfile,
  Company,
  DeliveryCapabilities,
  Job,
  OutreachMessage,
  Recruiter,
} from "@/lib/api";

interface PeopleOutreachWorkspaceProps {
  companies: Company[];
  onChanged: () => Promise<void>;
}

async function loadWorkspace() {
  const [people, jobs, messages, capabilities, profile] = await Promise.all([
    api.recruiters(),
    api.allJobs(),
    api.outreachMessages(),
    api.outreachCapabilities(),
    api.profile().catch(() => null),
  ]);
  return { people, jobs, messages, capabilities, profile };
}

export function PeopleOutreachWorkspace({
  companies,
  onChanged,
}: PeopleOutreachWorkspaceProps) {
  const [people, setPeople] = useState<Recruiter[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [messages, setMessages] = useState<OutreachMessage[]>([]);
  const [capabilities, setCapabilities] = useState<DeliveryCapabilities | null>(null);
  const [profile, setProfile] = useState<CandidateProfile | null>(null);
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
  const [selectedJobId, setSelectedJobId] = useState("");
  const [extraContext, setExtraContext] = useState("");
  const [draftBodies, setDraftBodies] = useState<Record<number, string>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    const data = await loadWorkspace();
    setPeople(data.people);
    setJobs(data.jobs);
    setMessages(data.messages);
    setCapabilities(data.capabilities);
    setProfile(data.profile);
    if (data.profile) {
      setResumeText(data.profile.resume_text);
      setPositioning(data.profile.positioning ?? "");
    }
    setDraftBodies(
      Object.fromEntries(data.messages.map((message) => [message.id, message.body])),
    );
  }, []);

  useEffect(() => {
    let active = true;
    void loadWorkspace()
      .then((data) => {
        if (!active) return;
        setPeople(data.people);
        setJobs(data.jobs);
        setMessages(data.messages);
        setCapabilities(data.capabilities);
        setProfile(data.profile);
        if (data.profile) {
          setResumeText(data.profile.resume_text);
          setPositioning(data.profile.positioning ?? "");
        }
        setDraftBodies(
          Object.fromEntries(data.messages.map((message) => [message.id, message.body])),
        );
      })
      .catch((caught: unknown) => {
        if (!active) return;
        setError(caught instanceof Error ? caught.message : "Could not load people and outreach.");
      });
    return () => {
      active = false;
    };
  }, []);

  const watchlist = companies.filter((company) => company.is_watchlisted);
  const shortlisted = people.filter((person) => person.is_shortlisted);
  const selectedPerson = people.find((person) => person.id === Number(selectedPersonId));
  const selectedCompanyJobs = useMemo(
    () =>
      selectedPerson
        ? jobs.filter((job) => job.company_id === selectedPerson.company_id)
        : [],
    [jobs, selectedPerson],
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
      setError(caught instanceof Error ? caught.message : "The action could not be completed.");
    } finally {
      setBusy(null);
    }
  }

  async function addPerson(event: FormEvent) {
    event.preventDefault();
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
      setNotice("Person added. Review the reply score and shortlist when ready.");
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
      setNotice("Resume profile saved for message personalization.");
    });
  }

  async function generateMessage(event: FormEvent) {
    event.preventDefault();
    await runAction("generate", async () => {
      await api.generateOutreach({
        recruiter_id: Number(selectedPersonId),
        job_id: Number(selectedJobId),
        extra_context: extraContext.trim() || undefined,
      });
      setExtraContext("");
      setNotice("A unique draft is ready for your review.");
    });
  }

  async function copyAndOpen(message: OutreachMessage) {
    await navigator.clipboard.writeText(message.body);
    window.open(message.recruiter.linkedin_url, "_blank", "noopener,noreferrer");
    setNotice("Message copied and LinkedIn opened. Send it there, then mark it sent here.");
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
          <h2>Find, score and shortlist the right people.</h2>
        </div>
        <span>{shortlisted.length} shortlisted</span>
      </div>

      <div className="workflow-grid">
        <form className="panel form-stack" onSubmit={addPerson}>
          <div className="panel__heading">
            <h3>Add a recruiter or hiring manager</h3>
            <span>Stored in Postgres</span>
          </div>
          <label>
            Company
            <select
              value={companyId}
              onChange={(event) => setCompanyId(event.target.value)}
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
          <div className="form-pair">
            <label>
              Name
              <input
                value={personName}
                onChange={(event) => setPersonName(event.target.value)}
                placeholder="Priya Sharma"
                required
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
              required
            />
          </label>
          <label>
            Recent activity or hiring signal
            <textarea
              value={activity}
              onChange={(event) => setActivity(event.target.value)}
              placeholder="Posted about hiring product managers this week"
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
          <button className="button button--dark" disabled={busy === "add-person"}>
            {busy === "add-person" ? "Adding…" : "Add person"}
          </button>
        </form>

        <div className="panel">
          <div className="panel__heading">
            <h3>People queue</h3>
            <span>Highest reply probability first</span>
          </div>
          <div className="people-list">
            {people.map((person) => {
              const company = companies.find((item) => item.id === person.company_id);
              const companyJobs = jobs.filter((job) => job.company_id === person.company_id);
              return (
                <article className="person-card" key={person.id}>
                  <div>
                    <p>{company?.name ?? "Company"}</p>
                    <h4>{person.name}</h4>
                    <span>{person.designation ?? "Designation pending"}</span>
                  </div>
                  <strong>{person.reply_probability ?? 0}%</strong>
                  <a href={person.linkedin_url} target="_blank" rel="noreferrer">
                    View profile ↗
                  </a>
                  {person.is_shortlisted ? (
                    <button
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
                    <label className="shortlist-control">
                      Job to discuss
                      <select
                        defaultValue=""
                        onChange={(event) => {
                          const jobId = Number(event.target.value);
                          if (!jobId) return;
                          void runAction(`shortlist-${person.id}`, () =>
                            api
                              .shortlistRecruiter(person.id, jobId)
                              .then(() => undefined),
                          );
                        }}
                      >
                        <option value="">Shortlist for…</option>
                        {companyJobs.map((job) => (
                          <option key={job.id} value={job.id}>
                            {job.title}
                          </option>
                        ))}
                      </select>
                    </label>
                  )}
                </article>
              );
            })}
            {people.length === 0 && (
              <div className="empty-state">
                <strong>No people stored yet.</strong>
                <p>Add a recruiter, hiring manager, or founder from a target company.</p>
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="workflow__heading workflow__heading--spaced" id="outreach">
        <div>
          <p className="eyebrow">Approval-first outreach</p>
          <h2>Generate, review, approve and track every message.</h2>
        </div>
        <span>
          {capabilities?.sent_today ?? 0}/{capabilities?.daily_limit ?? 10} sent today
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
            <h3>2. Generate message</h3>
            <span>No templates</span>
          </div>
          <label>
            Shortlisted person
            <select
              value={selectedPersonId}
              onChange={(event) => {
                setSelectedPersonId(event.target.value);
                setSelectedJobId("");
              }}
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
          <label>
            Job
            <select
              value={selectedJobId}
              onChange={(event) => setSelectedJobId(event.target.value)}
              required
            >
              <option value="">Choose job</option>
              {selectedCompanyJobs.map((job) => (
                <option key={job.id} value={job.id}>
                  {job.title}
                </option>
              ))}
            </select>
          </label>
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
            disabled={busy === "generate" || !profile}
          >
            {busy === "generate" ? "Writing…" : "Generate unique draft"}
          </button>
          {!profile && <p className="helper">Save the Rahul profile first.</p>}
        </form>

        <div className="panel delivery-panel">
          <div className="panel__heading">
            <h3>3. Delivery controls</h3>
            <span>{capabilities?.mode ?? "MANUAL"}</span>
          </div>
          <strong>
            {capabilities?.automatic_linkedin_send
              ? "Automatic delivery enabled"
              : "Approved handoff enabled"}
          </strong>
          <p>
            {capabilities?.reason ??
              "Approved messages will use the configured LinkedIn partner integration."}
          </p>
          <div className="limit-meter">
            <span
              style={{
                width: `${Math.min(
                  ((capabilities?.sent_today ?? 0) /
                    (capabilities?.daily_limit ?? 10)) *
                    100,
                  100,
                )}%`,
              }}
            />
          </div>
          <small>Daily cap protects outreach quality and keeps a clear audit trail.</small>
        </div>
      </div>

      <div className="message-queue">
        {messages.map((message) => (
          <article className="message-card" key={message.id}>
            <div className="message-card__meta">
              <div>
                <p>{message.job.company.name}</p>
                <h3>
                  {message.recruiter.name} · {message.job.title}
                </h3>
              </div>
              <span className={`status-badge status-badge--${message.status.toLowerCase()}`}>
                {message.status}
              </span>
            </div>
            <label>
              Personalized message preview
              <textarea
                value={draftBodies[message.id] ?? message.body}
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
            <div className="message-actions">
              {message.status === "DRAFT" && (
                <>
                  <button
                    className="button button--secondary"
                    onClick={() =>
                      runAction(`save-${message.id}`, () =>
                        api
                          .editOutreach(
                            message.id,
                            draftBodies[message.id] ?? message.body,
                          )
                          .then(() => undefined),
                      )
                    }
                  >
                    Save edit
                  </button>
                  <button
                    className="button button--primary"
                    onClick={() =>
                      runAction(`approve-${message.id}`, async () => {
                        await api.editOutreach(
                          message.id,
                          draftBodies[message.id] ?? message.body,
                        );
                        await api.approveOutreach(message.id);
                        setNotice("Message approved and ready for delivery.");
                      })
                    }
                  >
                    Approve
                  </button>
                </>
              )}
              {message.status === "APPROVED" && (
                <>
                  {capabilities?.automatic_linkedin_send ? (
                    <button
                      className="button button--primary"
                      onClick={() =>
                        runAction(`send-${message.id}`, () =>
                          api.autoSendOutreach(message.id).then(() => undefined),
                        )
                      }
                    >
                      Send approved DM
                    </button>
                  ) : (
                    <button
                      className="button button--primary"
                      onClick={() => copyAndOpen(message)}
                    >
                      Copy + open LinkedIn
                    </button>
                  )}
                  <button
                    className="button button--secondary"
                    onClick={() =>
                      runAction(`sent-${message.id}`, () =>
                        api.markOutreachSent(message.id).then(() => undefined),
                      )
                    }
                  >
                    Mark sent
                  </button>
                </>
              )}
              {message.status === "SENT" && (
                <button
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
            <strong>No message drafts yet.</strong>
            <p>Shortlist a person, save your profile, then generate the first unique message.</p>
          </div>
        )}
      </div>
    </section>
  );
}
