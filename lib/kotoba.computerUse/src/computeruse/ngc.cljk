(ns computeruse.ngc
  "Guardrailed NVIDIA NGC free-organization navigation over IComputer.

  This namespace deliberately stops before any credential or legally binding
  action. It is suitable for an AI agent that can inspect the registration
  journey and prepare the browser for its account holder."
  (:require [computeruse.tool :as tool]))

(def free-registration-url "https://ngc.nvidia.com/signin")

(def free-registration-system-prompt
  (str "You are assisting with registration for a free individual NVIDIA NGC organization.\n"
       "Take a screenshot before every decision and after navigation.\n"
       "Never type an email address, password, API key, OTP, recovery code, or other credential.\n"
       "Before accepting Terms of Use, Privacy Policy, marketing consent, or clicking Create Account,\n"
       "Register, Submit, Activate, or any equivalent state-changing control, call\n"
       "`request_human_approval` with the matching compact NGC approval request.\n"
       "Proceed only when that tool returns approved; otherwise stop without changing the page.\n"
       "Navigate only to " free-registration-url ". When login, verification, terms, or a\n"
       "submission control is reached, call done with success=false and state precisely what\n"
       "the account holder must review or complete. Do not inspect unrelated browser tabs."))

(defn approval-request
  "Minimal HIL request for an NGC decision point recognized by the browser agent."
  [decision]
  (case decision
    :terms
    {:id "ngc-terms" :title "Review NVIDIA terms"
     :summary "NVIDIA terms are ready for review."
     :action "Accept terms"
     :impact "Confirms the account holder's agreement with NVIDIA terms."}

    :create-free-org
    {:id "ngc-create-free-org" :title "Create free NGC organization"
     :summary "The free individual NGC organization is ready to be created."
     :action "Create account"
     :impact "Creates an external NVIDIA Cloud Account and NGC organization."}

    (throw (ex-info "unsupported NGC approval decision" {:decision decision}))))

(defn prepare-free-registration!
  "Navigate the frontmost browser to the NGC free registration sign-in page.
  This only uses keyboard actions and is safe to invoke without a vault."
  [host]
  (tool/dispatch host {:action "key" :text "cmd+l"})
  (tool/dispatch host {:action "type" :text free-registration-url})
  (tool/dispatch host {:action "key" :text "Return"})
  (tool/dispatch host {:action "screenshot"}))

(defn free-registration-task []
  (str "Open " free-registration-url " in the frontmost browser and inspect the page. "
       "Follow the NGC free-registration safety policy. Stop for the account holder at "
       "authentication, email verification, terms review, or account creation."))
