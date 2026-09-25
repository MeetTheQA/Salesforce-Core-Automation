"""Starter Salesforce Core feature memories.

These are user-editable scaffolds, not invented story facts. They are
applied only when a feature memory is empty. Provenance is always
``source_kind=user`` with ``source_note=seed_template:<id>``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from ai_qa_portal.backend.models.feature import FeatureMemoryFact

SEED_TEMPLATES: dict[str, dict] = {
    "account_management": {
        "name": "Account Management",
        "summary": "Customer and prospect account lifecycle, hierarchy, ownership, and sharing.",
        "facts": [
            ("business_rules", "Account create, edit, merge, and delete behavior must follow the story; do not assume a default owner or record type."),
            ("salesforce_objects", "Primary object is Account. Related objects commonly include Contact, Opportunity, Case, and Campaign Member via Contact/Lead."),
            ("permissions", "Record visibility depends on OWD, role hierarchy, sharing rules, and account teams. Missing access rules are open questions."),
            ("validation", "Required fields, duplicate rules, and parent-account constraints are story-specific. Do not invent field API names."),
            ("known_risks", "Hierarchy changes can reparent children and change visibility. Merges can lose related records if not specified."),
            ("open_questions", "Who can create, edit, and delete Accounts, and what happens to child Contacts and Opportunities?"),
        ],
    },
    "lead_management": {
        "name": "Lead Management",
        "summary": "Lead capture, assignment, conversion, and disqualification.",
        "facts": [
            ("business_rules", "Lead status transitions and conversion outcomes must come from the story or feature memory."),
            ("salesforce_objects", "Primary object is Lead. Conversion can create or match Account, Contact, and optionally Opportunity."),
            ("permissions", "Queue ownership, assignment rules, and convert permission are not implied unless stated."),
            ("validation", "Duplicate lead rules and required company/name fields must be confirmed before writing negative cases as facts."),
            ("known_risks", "Converting a lead that matches an existing Account can attach to the wrong record if match rules are unspecified."),
            ("open_questions", "What statuses exist, who can convert, and does conversion always create an Opportunity?"),
        ],
    },
    "opportunity_sales": {
        "name": "Opportunity and Sales Process",
        "summary": "Pipeline stages, products, forecasts, and close behavior.",
        "facts": [
            ("business_rules", "Stage names, probability, and close-won/lost requirements are defined only by provided stories or memory."),
            ("salesforce_objects", "Primary object is Opportunity, often with Opportunity Product, Price Book, Quote, and Account."),
            ("permissions", "Stage edits may be limited by profile, validation, or approval. Do not assume Sales Rep vs Manager rights."),
            ("validation", "Amount, close date, and product quantity rules must be quoted from inputs before they become test facts."),
            ("known_risks", "Moving backward in stage, editing closed opportunities, and multi-currency amounts are common gaps."),
            ("open_questions", "Can a closed Opportunity be edited, and which stages require products or approvals?"),
        ],
    },
    "campaign_management": {
        "name": "Campaign Management",
        "summary": "Campaign lifecycle, members, and influence on leads and contacts.",
        "facts": [
            ("business_rules", "Campaign status changes and member add/remove rules must be explicit. Closed or completed campaigns are often non-editable — confirm before asserting."),
            ("salesforce_objects", "Primary objects are Campaign and Campaign Member. Members relate to Lead or Contact, and Contact relates to Account."),
            ("permissions", "Marketing vs sales rights to create campaigns or add members are open unless stated."),
            ("validation", "Duplicate campaign members and start/end date order are common checks only when the story mentions them."),
            ("integrations", "Campaign influence on Opportunities is optional and must not be assumed."),
            ("known_risks", "Adding a Lead that later converts can change member identity from Lead to Contact."),
            ("open_questions", "Which campaign statuses block edits, and who can add Leads versus Contacts?"),
        ],
    },
    "contact_management": {
        "name": "Contact Management",
        "summary": "People records, account relationships, and communication preferences.",
        "facts": [
            ("business_rules", "A Contact is normally related to one Account unless the story defines indirect relationships."),
            ("salesforce_objects", "Primary object is Contact, related to Account, Campaign Member, Opportunity Contact Role, and Case."),
            ("permissions", "Who can edit email, phone, and opt-out fields must be stated."),
            ("validation", "Duplicate email and required Account rules are story-specific."),
            ("known_risks", "Deleting or merging a Contact can orphan campaign history and opportunity roles."),
            ("open_questions", "Is Account required, and what happens to roles when a Contact is merged?"),
        ],
    },
    "quotes": {
        "name": "Quotes",
        "summary": "Quote creation from opportunities, sync, and status.",
        "facts": [
            ("business_rules", "Quote sync to Opportunity and which quote is primary must be defined by the story."),
            ("salesforce_objects", "Primary object is Quote, related to Opportunity, Quote Line Item, Price Book, and Account."),
            ("permissions", "Who can create, sync, and accept a quote is an open question unless stated."),
            ("validation", "Discount limits, expired quotes, and line-item required fields must not be invented."),
            ("known_risks", "Syncing a quote can overwrite Opportunity amount and products."),
            ("open_questions", "Does accepting a quote update Opportunity stage, and can an expired quote be synced?"),
        ],
    },
    "sales_agreements": {
        "name": "Sales Agreements",
        "summary": "Agreement terms between the selling org and an Account, including products and schedules.",
        "facts": [
            ("business_rules", "Agreement activation, amendment, and cancellation rules come only from provided context."),
            ("salesforce_objects", "Sales Agreement relates to Account and agreement products. Do not assume a custom object API name."),
            ("permissions", "Who can activate or amend an agreement must be explicit."),
            ("validation", "Start/end dates, quantity commitments, and pricing tiers are open unless stated."),
            ("integrations", "Downstream order or rebate calculation is out of scope unless the story names it."),
            ("known_risks", "Overlapping agreements on the same Account and product can double-count commitments."),
            ("open_questions", "Can an active agreement be edited, and how does it relate to Account and rebates?"),
        ],
    },
    "rebate_programs": {
        "name": "Rebate Programs",
        "summary": "Program eligibility, accrual, and payout tied to accounts and agreements.",
        "facts": [
            ("business_rules", "Eligibility, accrual period, and payout approval must be taken from stories or user notes."),
            ("salesforce_objects", "Rebate program context typically depends on Account and may depend on Sales Agreement or Orders. Exact objects are story-specific."),
            ("permissions", "Who can enroll an Account or approve a payout is an open question by default."),
            ("validation", "Thresholds, product exclusions, and retroactive adjustments must not be invented."),
            ("known_risks", "Changing agreement dates or Account hierarchy can change which transactions qualify."),
            ("open_questions", "Which transactions qualify, and what happens when an Account is merged mid-period?"),
        ],
    },
    "products_pricebooks": {
        "name": "Products and Price Books",
        "summary": "Product catalog, price books, and entry activation.",
        "facts": [
            ("business_rules", "Standard vs custom price book usage must be stated before tests assert a price source."),
            ("salesforce_objects", "Product, Price Book, and Price Book Entry feed Opportunity products and Quotes."),
            ("permissions", "Who can activate a price book entry is not implied."),
            ("validation", "Currency, inactive products, and missing price book entries are common failure modes when mentioned."),
            ("known_risks", "An Opportunity without a price book cannot add products."),
            ("open_questions", "Which price book is required, and are inactive products blocked?"),
        ],
    },
    "activities_and_tasks": {
        "name": "Activities and Tasks",
        "summary": "Tasks and events on leads, contacts, accounts, and opportunities.",
        "facts": [
            ("business_rules", "Required follow-up tasks and due-date rules are story-specific."),
            ("salesforce_objects", "Task and Event relate to Lead, Contact, Account, or Opportunity via Who/What."),
            ("permissions", "Shared activity visibility follows the parent record unless the story says otherwise."),
            ("known_risks", "Converting a Lead moves open activities; unspecified behavior should stay an open question."),
            ("open_questions", "Are tasks required before stage change or lead conversion?"),
        ],
    },
}


def list_seed_templates() -> list[dict[str, str]]:
    return [
        {"id": key, "name": str(val["name"]), "summary": str(val["summary"])}
        for key, val in SEED_TEMPLATES.items()
    ]


def facts_for_template(template_id: str) -> list[FeatureMemoryFact]:
    spec = SEED_TEMPLATES.get(template_id)
    if spec is None:
        raise KeyError(template_id)
    now = datetime.now(UTC)
    note = f"seed_template:{template_id}"
    facts = [
        FeatureMemoryFact(
            id=str(uuid4()),
            section="summary",
            text=str(spec["summary"]),
            source_kind="user",
            source_story_keys=[],
            source_note=note,
            created_at=now,
            updated_at=now,
        )
    ]
    for section, text in spec["facts"]:
        facts.append(
            FeatureMemoryFact(
                id=str(uuid4()),
                section=section,
                text=text,
                source_kind="user",
                source_story_keys=[],
                source_note=note,
                created_at=now,
                updated_at=now,
            )
        )
    return facts
