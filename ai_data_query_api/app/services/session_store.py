from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from threading import RLock
from typing import Optional
from uuid import uuid4

import pandas as pd


@dataclass
class DatasetRecord:
    dataset_id: str
    source_name: str
    dataframes: dict[str, pd.DataFrame]
    active_sheet: str
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class SessionRecord:
    session_id: str
    datasets: dict[str, DatasetRecord] = field(default_factory=dict)
    history: list[dict[str, str]] = field(default_factory=list)
    updated_at: datetime = field(default_factory=datetime.utcnow)


class InMemorySessionStore:
    def __init__(self, ttl_minutes: int = 60, history_max_messages: int = 20) -> None:
        self._ttl = timedelta(minutes=ttl_minutes)
        self._history_max_messages = max(1, history_max_messages)
        self._sessions: dict[str, SessionRecord] = {}
        self._lock = RLock()

    def _cleanup_expired(self) -> None:
        now = datetime.utcnow()
        expired_keys = [
            session_id
            for session_id, session in self._sessions.items()
            if now - session.updated_at > self._ttl
        ]
        for key in expired_keys:
            self._sessions.pop(key, None)

    def create_or_get_session(self, session_id: Optional[str] = None) -> SessionRecord:
        with self._lock:
            self._cleanup_expired()
            key = session_id or str(uuid4())
            if key not in self._sessions:
                self._sessions[key] = SessionRecord(session_id=key)
            self._sessions[key].updated_at = datetime.utcnow()
            return self._sessions[key]

    def add_dataset(
        self,
        session_id: str,
        source_name: str,
        dataframes: dict[str, pd.DataFrame],
        active_sheet: str,
    ) -> DatasetRecord:
        with self._lock:
            session = self.create_or_get_session(session_id)
            dataset = DatasetRecord(
                dataset_id=str(uuid4()),
                source_name=source_name,
                dataframes=dataframes,
                active_sheet=active_sheet,
            )
            session.datasets[dataset.dataset_id] = dataset
            session.updated_at = datetime.utcnow()
            return dataset

    def get_dataset(
        self,
        session_id: str,
        dataset_id: Optional[str] = None,
        sheet_name: Optional[str] = None,
    ) -> tuple[str, pd.DataFrame]:
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                raise KeyError("Session not found")

            if dataset_id:
                dataset = session.datasets.get(dataset_id)
                if not dataset:
                    raise KeyError("Dataset not found")
            else:
                if not session.datasets:
                    raise KeyError("No dataset found in session")
                # Latest inserted dataset.
                dataset = next(reversed(session.datasets.values()))

            selected_sheet = sheet_name or dataset.active_sheet
            if selected_sheet not in dataset.dataframes:
                raise KeyError(f"Sheet '{selected_sheet}' not found")

            session.updated_at = datetime.utcnow()
            return dataset.dataset_id, dataset.dataframes[selected_sheet]

    def get_dataset_meta(self, session_id: str, dataset_id: str) -> DatasetRecord:
        with self._lock:
            session = self._sessions.get(session_id)
            if not session or dataset_id not in session.datasets:
                raise KeyError("Dataset not found")
            return session.datasets[dataset_id]

    def add_history(self, session_id: str, question: str, answer: str) -> None:
        with self._lock:
            session = self.create_or_get_session(session_id)
            session.history.append({"question": question, "answer": answer})
            if len(session.history) > self._history_max_messages:
                session.history = session.history[-self._history_max_messages :]
            session.updated_at = datetime.utcnow()

    def get_history(self, session_id: str) -> list[dict[str, str]]:
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return []
            return list(session.history)
