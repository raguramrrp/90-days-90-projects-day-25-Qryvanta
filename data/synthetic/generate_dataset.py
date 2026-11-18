"""
Deterministic synthetic customer support dataset generator for QRYVANTA.
IMPORTANT: All generated records are explicitly marked `is_demo_data=True` and
`dataset_source='synthetic_demo_v1'` so synthetic demonstrations are never confused
with real production customer activity.
"""

from pathlib import Path
import random
from typing import Dict, List, Tuple
import pandas as pd


TAXONOMY: Dict[str, Dict[str, List[Tuple[str, str]]]] = {
    "Billing and Payments": {
        "Refund Request": [
            ("Requesting full refund for cancelled service", "I cancelled my annual workspace plan last week before renewal and need a refund issued back to my Visa card."),
            ("Need refund after duplicate invoice settlement", "Our accounting team accidentally settled invoice twice and requests a credit refund to the original payment method."),
            ("Refund status for returned hardware kit", "The warehouse confirmed receipt of my returned kit ten days ago, yet no refund appears on my statement."),
            ("Reimbursement request for unused subscription days", "We downgraded mid-cycle and were told unused prepaid days would be refunded back to our corporate card."),
            ("Partial refund needed for billing discrepancy", "Promotional discount code was not applied at checkout so I am asking for a partial refund of the difference."),
            ("Money back request for failed workshop booking", "The online training session was rescheduled and I cannot attend, please process a refund promptly."),
            ("Credit memo refund to original bank transfer", "Please reimburse our overpayment from last month via ACH transfer to our registered finance account."),
            ("Follow up on approved refund not received", "Support approved my refund two weeks ago under ticket confirmation but the funds have not cleared."),
        ],
        "Payment Failure": [
            ("Credit card declined during checkout renewal", "Every attempt to pay our monthly balance using our active Mastercard fails with gateway error code 402."),
            ("Wire transfer payment not reflecting on portal", "We submitted an international bank wire three business days ago and the billing portal still shows unpaid."),
            ("Unable to update expired corporate payment card", "When entering our new debit card details in billing settings the payment processor rejects valid CVV input."),
            ("Auto-debit transaction failed unexpectedly", "Our scheduled autopay failed even though sufficient funds exist and the issuing bank saw no block."),
            ("SEPA direct debit mandate rejected at checkout", "Attempting to configure SEPA direct debit for recurring European billing returns an invalid IBAN failure."),
            ("Apple Pay checkout freezes on confirmation", "Trying to pay for an add-on bundle through Apple Pay times out and never completes the charge."),
            ("Invoice payment link returns gateway timeout", "Clicking the Pay Now link in our PDF invoice opens a blank screen with payment processor timeout."),
            ("Declined ACH settlement on recurring invoice", "Our ACH routing number was verified last quarter yet this month's automatic debit failed twice."),
        ],
        "Incorrect Charge": [
            ("Double charged on monthly billing statement", "My bank statement shows two identical charges of 149 dollars processed on the same afternoon."),
            ("Unexpected overage fee on October invoice", "We stayed well below our API quota yet the latest invoice includes an unexpected usage overage charge."),
            ("Wrong VAT tax rate applied to EU invoice", "We entered our valid European VAT registration ID but the invoice still charged 20 percent tax."),
            ("Charged after trial cancellation confirmation", "I cancelled during the 14-day free trial and received confirmation, yet my card was billed today."),
            ("Incorrect seat count billed on quarterly statement", "We removed four former staff accounts last month but are still being billed for all twelve seats."),
            ("Unknown recurring charge on corporate card", "Our finance department spotted an unrecognized monthly charge from your billing descriptor."),
            ("Currency conversion mismatch on invoice total", "Our contract specifies EUR pricing, however this invoice billed in USD at an inflated amount."),
            ("Late fee charged despite on-time payment", "We remitted payment five days before the due date yet a late penalty fee was added to our account."),
        ],
    },
    "Technical Support": {
        "Application Error": [
            ("HTTP 500 internal server error saving reports", "Whenever I click export to PDF in the reporting module the web app throws a 500 internal server error."),
            ("Desktop client crashes immediately on startup", "After updating to version 4.2 the Windows desktop client crashes with an unhandled null reference exception."),
            ("Dashboard filters freeze browser tab completely", "Applying more than two date filters on the analytics screen causes the page to hang and stop responding."),
            ("API webhook payloads returning malformed JSON", "Our integration endpoint started receiving truncated JSON payloads from event webhooks since yesterday."),
            ("Blank white screen after submitting workflow form", "Submitting a multi-step approval form leads to a blank white screen and console TypeError messages."),
            ("CSV export downloads empty zero-byte file", "Exporting filtered customer logs produces a 0 KB file across both Chrome and Edge browsers."),
            ("Mobile iOS app force closes when uploading photo", "Attaching a screenshot from the camera roll on iOS 18 immediately closes the mobile application."),
            ("Database sync job failing with schema mismatch", "Nightly connector synchronization aborts midway with column type mismatch error in sync logs."),
        ],
        "Installation Issue": [
            ("Windows installer fails with missing DLL error", "Running the MSI package on Windows 11 stops at 60 percent citing a missing VCRUNTIME140 library."),
            ("Docker container fails health check during deploy", "Our self-hosted deployment container exits with code 137 immediately after running database migrations."),
            ("CLI package installation blocked by dependency conflict", "Installing the official Python SDK fails due to conflicting urllib3 version constraints."),
            ("macOS Gatekeeper blocks desktop agent setup", "The signed DMG installer cannot complete initialization on Apple Silicon M3 laptops."),
            ("SSO SAML plugin configuration fails metadata import", "Uploading our Okta XML metadata file during initial setup returns invalid certificate chain error."),
            ("Browser extension fails to register native host", "The Chrome enterprise extension installs cleanly but reports native messaging host unreachable."),
            ("Linux systemd service fails to start after install", "Following the Ubuntu apt install guide, systemctl start fails with permission denied on config file."),
            ("Excel add-in not appearing in ribbon after setup", "We ran the Office 365 add-in installer for finance users but the toolbar tab never loads."),
        ],
        "Performance Issue": [
            ("Severe query latency on main search bar", "Searching customer records now takes over 18 seconds compared to under 1 second last week."),
            ("API response times spiking above 10 seconds", "Production REST calls to the orders endpoint are timing out intermittently during business hours."),
            ("High CPU usage from background sync daemon", "The local sync agent consumes 95 percent CPU continuously even when no files are changing."),
            ("Report generation queue stalled for two hours", "Scheduled weekly summary jobs stay in queued state for hours before timing out."),
            ("Memory leak in live monitoring dashboard", "Leaving the operations screen open for two hours grows browser RAM usage past 4 GB."),
            ("Slow file upload speeds across regional servers", "Uploading a 3 MB PDF attachment takes more than two minutes on a gigabit office connection."),
            ("Bulk import job crawling at five rows per minute", "Importing a standard 500-row spreadsheet now stalls halfway through with heavy database lag."),
            ("Video call widget stuttering with packet loss", "Embedded support screen-sharing freezes every ten seconds with high latency warnings."),
        ],
    },
    "Account and Login": {
        "Password Reset": [
            ("Password reset email never arrives in inbox", "I requested a password reset link three times today and checked spam folders but nothing arrived."),
            ("Password reset token says expired immediately", "Clicking the recovery link within two minutes of receiving it displays an invalid or expired token alert."),
            ("Unable to change password in security settings", "Entering my current password and a compliant new passphrase throws an unexpected validation failure."),
            ("Forgot credentials for legacy admin portal", "Our former IT coordinator left and we need a verified password reset for the primary admin email."),
            ("Password update loop forces repeated login", "After successfully setting a new password the sign-in screen keeps redirecting back to reset password."),
            ("Corporate email filter stripped password reset URL", "Security scanning invalidated the single-use password reset link before I could open it."),
            ("Cannot reset PIN for mobile app sign-in", "The forgot passcode workflow on Android sends a blank email without a recovery button."),
            ("Password complexity validator rejects strong phrase", "My 20-character password with symbols is rejected as invalid during mandatory rotation."),
        ],
        "Account Lockout": [
            ("Account locked after failed SSO attempts", "Following an identity provider outage my account is locked out and says contact support to unlock."),
            ("User profile accidentally suspended by system", "My workspace login displays account suspended even though our organization subscription is active."),
            ("Too many failed login attempts lockout timer stuck", "I waited over two hours after mistyping my password yet the lockout banner will not clear."),
            ("Admin locked out after IP allowlist misconfiguration", "I mistyped our office CIDR range in security restrictions and locked all administrators out."),
            ("Multiple team members locked out simultaneously", "Five support staff in our regional office were automatically locked out after VPN rotation."),
            ("Reactivate deactivated employee account needed", "A returning contractor needs their previously archived login reactivated with existing permissions."),
            ("Brute force protection blocked legitimate API user", "Our automated service account was locked following a credential rotation window."),
            ("Account disabled notice upon fresh sign-in", "I just accepted my organization invitation and immediately saw an account disabled message."),
        ],
        "Verification Issue": [
            ("Two-factor authentication SMS code not received", "I am not receiving the 6-digit SMS OTP code on my registered mobile number when signing in."),
            ("Authenticator app TOTP codes rejected as invalid", "Google Authenticator codes fail verification every time despite syncing device clock."),
            ("Lost phone need MFA recovery reset", "My phone was replaced and I do not have my backup recovery codes to pass two-factor login."),
            ("Email verification link returns 404 not found", "After registering a new customer account the confirmation link opens a broken page."),
            ("Hardware security key WebAuthn prompt failing", "My YubiKey is not recognized during enterprise login verification on Firefox."),
            ("Domain ownership TXT verification stuck pending", "We added the DNS TXT record 48 hours ago but organization domain verification still fails."),
            ("Identity verification document upload rejected", "Uploaded business registration PDF for KYC check failed automated readability verification."),
            ("SSO email attribute mismatch preventing login", "Okta authentication succeeds but QRYVANTA fails verification due to uppercase email mismatch."),
        ],
    },
    "Delivery and Shipping": {
        "Delayed Delivery": [
            ("Express shipment three days past delivery estimate", "We paid for next-day courier delivery for our hardware order and it is now three days overdue."),
            ("International parcel held at customs clearance", "Our shipment to Toronto has remained at customs processing for six days without release updates."),
            ("Scheduled freight delivery missed appointment window", "The warehouse crew waited all morning for the pallet delivery that never arrived as scheduled."),
            ("Order stuck at regional sorting facility for a week", "Carrier scan shows my package sitting at the Memphis hub since last Monday with no movement."),
            ("Urgent replacement unit delayed in transit", "Our replacement terminal was promised by Friday and the updated estimate pushed to next Wednesday."),
            ("Weather delay notice without revised arrival date", "Tracking mentions an operational delay five days ago and provides no new estimated delivery date."),
            ("Priority shipping downgraded to ground service", "I paid for two-day air shipping but the parcel was dispatched via standard ground taking eight days."),
            ("Split shipment second box severely delayed", "Box one of two arrived Tuesday but the second box containing cables has been delayed indefinitely."),
        ],
        "Missing Package": [
            ("Package marked delivered but nowhere at address", "Carrier tracking states left at front reception at 2 PM, yet our security desk received nothing."),
            ("Shipment lost in transit according to carrier", "The courier helpline told me the parcel could not be located after leaving the distribution hub."),
            ("Delivered to wrong street address in proof photo", "The delivery confirmation photo shows an unfamiliar porch that does not match our office building."),
            ("Missing box from multi-parcel office delivery", "Only two of the three cartons listed on the packing slip were handed over by the driver."),
            ("Parcel never arrived after ten business days", "My order shipped two weeks ago with no scans after pickup and appears completely lost."),
            ("Signed delivery confirmation by unknown recipient", "Tracking claims someone named Alex signed for the parcel, but nobody by that name works here."),
            ("Courier left package outside in rain and it vanished", "Delivery instructions required a signature, yet the box was left unattended and is missing."),
            ("Replacement shipment missing after address correction", "Even after updating the suite number the re-dispatched package never reached our mailroom."),
        ],
        "Tracking Issue": [
            ("Tracking number shows not found on carrier site", "I received a dispatch email 48 hours ago, yet the tracking code returns invalid number."),
            ("Tracking status stuck on label created for four days", "The shipping label was generated Monday morning but the carrier has still not scanned pickup."),
            ("Wrong courier link attached to shipment email", "The tracking link points to FedEx while the tracking number format belongs to UPS."),
            ("Live delivery map not updating coordinates", "The same-day courier tracking link froze at 10 AM and has not refreshed for four hours."),
            ("Duplicate tracking numbers assigned to separate orders", "Two unrelated orders placed this week display the exact same airway bill tracking ID."),
            ("Customs tracking checkpoint missing invoice papers", "Carrier portal asks for commercial invoice upload to clear tracking hold."),
            ("No tracking notification sent after order marked shipped", "Portal shows status shipped yesterday but no tracking number or carrier name is listed."),
            ("Tracking shows returning to sender unexpectedly", "Without any delivery attempt our package tracking suddenly changed to returning to shipper."),
        ],
    },
    "Orders and Returns": {
        "Order Cancellation": [
            ("Cancel unshipped order before warehouse dispatch", "I accidentally ordered the wrong configuration an hour ago and need the order cancelled before pickup."),
            ("Request to cancel duplicate purchase order", "Our procurement clerk submitted the same purchase order twice; please cancel the second order."),
            ("Cancel backordered item from open order", "One item is backordered for six weeks so please cancel that line item and ship the rest."),
            ("Unable to find cancel button on pending order", "My order still shows processing status but the portal does not allow self-service cancellation."),
            ("Cancel pre-order before release billing date", "Please cancel my pre-order scheduled for next month and release the card authorization hold."),
            ("Bulk order cancellation due to project postponement", "Our office rollout was postponed so we must cancel order before freight scheduling."),
            ("Cancel order placed with incorrect shipping address", "I entered an old office address and want to cancel this order so I can place a fresh one."),
            ("Confirm cancellation of order requested by phone", "I spoke with sales earlier to cancel my order and need written confirmation it is voided."),
        ],
        "Return Request": [
            ("Need prepaid return shipping label for order", "The docking station is incompatible with our laptops and I would like an RMA return label."),
            ("Initiate return within 30-day satisfaction window", "We decided not to keep the unopened scanner kit and want to start a standard return."),
            ("Return authorization form not downloading", "Clicking generate RMA slip in order history fails so I cannot include the return barcode."),
            ("Return multiple items from two separate orders", "Can we consolidate returned accessories from two recent orders into a single return shipment?"),
            ("Return drop-off QR code expired before visit", "My printerless return QR code expired yesterday; please reissue a fresh return authorization."),
            ("Requesting return pickup for heavy office equipment", "The returned server rack unit weighs 40 kg and requires scheduled courier pickup from our loading bay."),
            ("Status of returned item delivered to returns center", "Tracking confirms our return reached your warehouse Monday; please confirm inspection status."),
            ("Return policy exception for unopened corporate batch", "We are three days past the 30-day window on two sealed boxes and request return approval."),
        ],
        "Exchange Request": [
            ("Exchange wrong size protective sleeve ordered", "I ordered the 13-inch laptop sleeve by mistake and would like to exchange it for the 15-inch model."),
            ("Swap EU power adapter kit for US plug version", "Our shipment included European plug adapters; please arrange an exchange for North American units."),
            ("Exchange color variant for unopened headset", "We received matte black headsets and want to exchange them for the silver edition."),
            ("Request direct exchange for higher storage tier", "Can I exchange my unopened 512 GB drive for the 1 TB model and pay the price difference?"),
            ("Exchange wrong model sent in warehouse fulfillment", "Packing slip lists model Pro-200 but the box contained Standard-100; please send the correct item."),
            ("Exchange defective keyboard for replacement layout", "While exchanging my faulty keyboard could we switch from UK ISO layout to US ANSI layout?"),
            ("Fast-track advance exchange for critical branch kit", "We need an advance replacement exchange shipped immediately while we return the mismatched unit."),
            ("Check dispatch status of approved exchange order", "My original item was scanned back at your hub and I am waiting on the replacement exchange shipment."),
        ],
    },
    "Product Issues": {
        "Defective Item": [
            ("Device powers off randomly after five minutes", "The newly delivered barcode scanner shuts down spontaneously even with a fully charged battery."),
            ("Cracked LCD display right out of sealed box", "Upon unboxing the monitor today we noticed a diagonal hairline crack and dead vertical pixels."),
            ("Charging port loose and fails to hold USB-C cable", "The USB-C power connector wobbles and disconnects unless held at a sharp angle."),
            ("Thermal printer producing blank faded receipts", "Brand new receipt printer feeds paper smoothly but outputs completely unreadable faint stripes."),
            ("Audio headset microphone produces loud static", "Colleagues hear harsh buzzing noise whenever the boom mic is unmuted on the new headset."),
            ("Smart sensor module fails calibration self-test", "Unit flashes red error LED continuously during initial pairing and fails factory diagnostic."),
            ("Battery swelling noticed after two months of use", "The tablet casing is separating slightly near the battery compartment and getting unusually hot."),
            ("Touchscreen unresponsive on right half of panel", "Half of the kiosk display does not register finger input even after factory reset."),
        ],
        "Missing Parts": [
            ("Power adapter cable missing from retail box", "We received the main terminal unit and manual, but the AC power brick and cord were missing."),
            ("Mounting bracket screws absent from hardware kit", "The wall mount plate was included in the parcel without the four VESA screws or anchors."),
            ("Only one wireless receiver included in dual pack", "The two-pack conference mic bundle only contained one USB dongle inside the sealed foam tray."),
            ("Missing user quick-start card and calibration tool", "The precision sensor box lacked the magnetic calibration key needed for setup."),
            ("Protective carrying pouch omitted from order", "Product listing specifies a travel case included with the Pro kit, which was not in the box."),
            ("Incomplete cable harness in replacement kit", "The Ethernet patch cord and serial adapter were missing from the accessories bag."),
            ("Missing battery cover door on handheld reader", "Handheld barcode reader arrived without the rear latch cover for the battery slot."),
            ("Spare ear tips and charging cradle missing", "Only the headset itself arrived; the desk charging dock and ear cushions were absent."),
        ],
        "Quality Concern": [
            ("Visible scratches on supposedly brand new chassis", "The aluminum enclosure arrived with deep scuff marks looking like a refurbished unit."),
            ("Packaging arrived crushed with bent enclosure corner", "Outer box had no protective foam padding and the metal housing corner is visibly dented."),
            ("Material finish peeling after one week of office use", "Soft-touch coating on the ergonomic mouse is already flaking off after minimal desk use."),
            ("Product specifications do not match catalog sheet", "Listing promised aluminum alloy hinges, yet the delivered stand uses flimsy molded plastic."),
            ("Strong chemical odor from protective desk mat", "The neoprene mat emits an overpowering rubber smell even after airing out for days."),
            ("Inconsistent LED brightness across matched panels", "We ordered four identical status displays and one has a noticeably yellow color tint."),
            ("Loose rattling sound inside sealed docking unit", "Shaking the dock gently reveals a loose screw or component rattling inside the casing."),
            ("Printed keycap legends wearing off prematurely", "Letters on the frequently used keys faded away within three weeks of normal typing."),
        ],
    },
    "Subscription Management": {
        "Plan Upgrade or Downgrade": [
            ("Upgrade team workspace from Growth to Enterprise", "We need SAML SSO and custom SLA policies, so please upgrade our workspace to Enterprise tier."),
            ("Downgrade subscription before next annual renewal", "Our seasonal project finished and we want to move from Professional down to Starter plan next cycle."),
            ("Proration calculation question for mid-year upgrade", "If we switch from monthly Pro to annual Business today how is our remaining credit prorated?"),
            ("Enable sandbox environment add-on on current plan", "We would like to add the staging sandbox module to our existing Business subscription."),
            ("Switch billing frequency from monthly to annual", "Please convert our current monthly billing cadence to annual invoicing for the 15 percent discount."),
            ("Upgrade API rate limit tier for peak traffic", "Upcoming marketing launch requires upgrading our API throughput package for next quarter."),
            ("Downgrade storage add-on tier after archive cleanup", "We deleted old media backups and want to drop from 5 TB storage tier back to 1 TB."),
            ("Compare Enterprise features before tier upgrade", "Before approving an upgrade please confirm whether audit log retention is included in Business."),
        ],
        "Subscription Cancellation": [
            ("Cancel recurring subscription before renewal date", "Please turn off auto-renewal and cancel our workspace subscription at the end of this billing period."),
            ("Stop auto-renew on legacy personal account", "I no longer use the personal plan and cannot locate the toggle to disable automatic renewal."),
            ("Request written confirmation of subscription termination", "Our compliance team requires a PDF confirmation that our SaaS contract will not auto-renew."),
            ("Cancel add-on analytics module only", "We want to keep our core support seats active but cancel the optional BI connector add-on."),
            ("Pause subscription temporarily for two months", "Our small business is closed over winter; can we pause recurring billing instead of cancelling?"),
            ("Consolidate two subscriptions and cancel duplicate", "After merging regional teams we need to cancel the redundant subsidiary subscription."),
            ("Cancel trial before conversion to paid plan", "Please terminate our evaluation workspace before day 14 so no paid subscription activates."),
            ("Export data archive prior to subscription closure", "We plan to cancel next month and need guidance on exporting all historical tickets before closure."),
        ],
        "Seat or License Change": [
            ("Add five new agent seats to workspace license", "We hired five new support specialists starting Monday and need five additional licensed seats."),
            ("Remove inactive user licenses before renewal", "Three team members departed and we need to reduce our licensed seat count from 25 to 22."),
            ("Transfer floating license key to replacement workstation", "A developer laptop was replaced and we need to deactivate the old machine license slot."),
            ("Reached maximum user seat limit error inviting staff", "Attempting to invite a new manager displays seat quota exceeded despite deleting an old user."),
            ("Convert read-only viewer seat to full agent seat", "Please upgrade one light-viewer license to a full operational agent seat immediately."),
            ("Provision enterprise volume license keys for 40 users", "Our IT team needs the consolidated volume license activation file for our new regional branch."),
            ("Reclaim unassigned licenses billed on account", "Our license dashboard shows 30 paid seats but only 24 assigned; please adjust next cycle."),
            ("Temporary seasonal seats for holiday support surge", "Can we add ten short-term agent licenses for November and December only?"),
        ],
    },
    "General Enquiries": {
        "Product Information": [
            ("Question about SOC 2 compliance and data residency", "Does your platform support EU-only data residency and provide an up-to-date SOC 2 Type II report?"),
            ("Clarification on REST API webhooks and rate limits", "Could you share documentation detailing webhook retry policies and per-minute API rate limits?"),
            ("Request product demo for 50-seat customer ops team", "We are evaluating support platforms for our regional team and would like a guided walkthrough."),
            ("Compatibility question with Salesforce and Jira", "Does QRYVANTA offer native bidirectional syncing with Salesforce Service Cloud and Jira Software?"),
            ("Pricing inquiry for academic and nonprofit teams", "We run a university IT helpdesk and want to know whether educational pricing tiers are available."),
            ("Supported languages for ticket classification model", "Does your automated text classification currently support Spanish and French customer tickets?"),
            ("Browser compatibility matrix for enterprise rollout", "Could you confirm the minimum supported versions of Chrome, Edge, and Safari for agent workspaces?"),
            ("Clarify retention window for uploaded attachments", "How long are customer-uploaded PDFs and screenshots stored before archival deletion?"),
        ],
        "Policy Question": [
            ("GDPR right-to-erasure data deletion procedure", "How can a European customer submit a formal GDPR data erasure request and what is the SLA?"),
            ("Warranty coverage terms for refurbished accessories", "Does the standard 12-month hardware warranty also apply to certified refurbished replacement units?"),
            ("Clarify data processing addendum signing process", "Our legal counsel needs to countersign your standard DPA before onboarding our finance team."),
            ("Refund eligibility terms for annual enterprise contracts", "Could you point us to the exact clause covering mid-term cancellation on annual agreements?"),
            ("Accessibility WCAG 2.1 AA conformance statement", "Do you publish a current VPAT or accessibility conformance report for the customer portal?"),
            ("Acceptable use guidelines for automated bulk imports", "Are there policy limits on scheduling hourly bulk CSV ticket imports via the API?"),
            ("Subprocessor list update notification policy", "How do customers subscribe to advance notices when new infrastructure subprocessors are added?"),
            ("Invoice payment terms Net 30 eligibility requirements", "What minimum annual contract value is required to qualify for Net 30 invoice payment terms?"),
        ],
        "Partnership or Feedback": [
            ("Interested in becoming a certified regional reseller", "Our consulting firm implements CRM systems across APAC and would like to discuss partner onboarding."),
            ("Feature suggestion for customizable keyboard shortcuts", "Our power agents would love configurable keyboard shortcuts for closing and tagging tickets faster."),
            ("Integration partnership proposal from telephony vendor", "We build cloud VoIP software and would like to explore an official CTI connector partnership."),
            ("Positive feedback on clean ticket workspace layout", "Wanted to share that our support leads really appreciate the new three-column ticket workspace."),
            ("Academic research collaboration inquiry on NLP", "I am a university researcher exploring anonymized ticketing benchmarks and wanted to connect."),
            ("Suggestion to add dark-contrast print stylesheet", "When printing ticket transcripts for compliance audits a compact print layout would be very helpful."),
            ("Affiliate program inquiry for SaaS review publication", "Do you operate an official referral or affiliate partner program for B2B operations blogs?"),
            ("Feedback requesting scheduled weekly digest emails", "Managers would find an automated Monday morning SLA summary email very useful."),
        ],
    },
}

CONTEXT_PREFIXES = [
    "",
    "Hello support team, ",
    "Hi there, ",
    "Good morning, ",
    "Quick question: ",
    "Following up on our account: ",
    "For our operations workspace: ",
]

CONTEXT_SUFFIXES = [
    "",
    " Please advise on next steps.",
    " Let us know what additional details you need.",
    " Thank you for looking into this.",
    " We noticed this starting earlier today.",
    " Reference workspace account verified.",
    " Appreciate your help resolving this quickly.",
]

SUBJECT_VARIANTS = [
    "{subj}",
    "Need assistance: {subj}",
    "Issue report - {subj}",
    "Question regarding {subj_lower}",
]


def generate_synthetic_dataset(output_path: Path, seed: int = 42) -> pd.DataFrame:
    """
    Generate a balanced, deduplicated synthetic dataset across all 8 categories
    and 24 subcategories (approx. 576+ distinct samples).
    Clearly marked as synthetic demo data.
    """
    rng = random.Random(seed)
    rows: List[Dict[str, object]] = []
    seen_texts = set()
    record_idx = 1

    for category, sub_map in TAXONOMY.items():
        for subcategory, templates in sub_map.items():
            for t_idx, (base_subj, base_desc) in enumerate(templates):
                group_id = f"{category[:4].upper()}-{subcategory[:4].upper()}-{t_idx:02d}"
                # Generate 3 distinct phrasings per template, sharing template_group_id
                # so the training pipeline keeps entire groups strictly in train OR test (zero template leakage).
                chosen_variants = rng.sample(range(len(SUBJECT_VARIANTS)), 3)
                for v_idx in chosen_variants:
                    subj_fmt = SUBJECT_VARIANTS[v_idx]
                    subj = subj_fmt.format(subj=base_subj, subj_lower=base_subj[0].lower() + base_subj[1:])
                    prefix = rng.choice(CONTEXT_PREFIXES)
                    suffix = rng.choice(CONTEXT_SUFFIXES)
                    desc = f"{prefix}{base_desc}{suffix}".strip()
                    sig = f"{subj.lower()}||{desc.lower()}"
                    if sig in seen_texts:
                        continue
                    seen_texts.add(sig)
                    rows.append(
                        {
                            "record_id": f"SYN-{record_idx:04d}",
                            "template_group_id": group_id,
                            "subject": subj,
                            "description": desc,
                            "category": category,
                            "subcategory": subcategory,
                            "is_demo_data": True,
                            "dataset_source": "synthetic_demo_v1",
                        }
                    )
                    record_idx += 1

    df = pd.DataFrame(rows)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False, encoding="utf-8")
    return df


if __name__ == "__main__":
    out = Path(__file__).resolve().parent / "synthetic_support_tickets.csv"
    generated = generate_synthetic_dataset(out)
    print(f"Generated {len(generated)} synthetic demo tickets at {out}")
    print(generated["category"].value_counts())
