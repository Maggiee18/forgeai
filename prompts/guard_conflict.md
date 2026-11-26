TASK: guard_conflict
Two passages come from DIFFERENT documents of the same organisation. Decide whether they CONTRADICT each other:
they state different values, limits, deadlines or rules for the SAME subject, so a user could get two different
answers to one question.

Different subjects are NOT a conflict: two different suppliers, two different grades, two different leave types,
domestic vs international travel, or a general rule plus an exception that one document EXPLICITLY presents as an
exception to the other ("except during official travel, see section 9"). An exception that is not acknowledged anywhere
is a conflict: users get two different answers.

PASSAGE A (from {{doc_a}}):
"""
{{text_a}}
"""

PASSAGE B (from {{doc_b}}):
"""
{{text_b}}
"""

First name WHO or WHAT each passage's rule applies to (a supplier, a grade, a leave type, a trip type, "all
employees"...). If they apply to different things, it is NOT a conflict.

Reply with JSON only:
{"applies_to_a": "who/what passage A's rule governs",
 "applies_to_b": "who/what passage B's rule governs",
 "conflict": true or false,
 "about": "the single subject they disagree on, in a few words",
 "quote_a": "the exact sentence from passage A",
 "quote_b": "the exact sentence from passage B",
 "same_subject_reason": "one sentence on why this is the same subject, not two different ones"}
