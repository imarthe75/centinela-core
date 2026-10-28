"""Verifiers: each "mandatory constraint" of a spec as a script that answers CUMPLE / NO_CUMPLE / NO_EVALUADO (ADR-0003 D4).

NO_EVALUADO is a first-class answer: when a check cannot be decided from the files it can see (no SQL, unsupported language, heuristic too weak)
it says so. It never degrades to CUMPLE. Heuristic verifiers say they are heuristic in their `method`.
"""
