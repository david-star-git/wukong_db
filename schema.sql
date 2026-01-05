PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS workers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    display_name TEXT NOT NULL,
    normalized_name TEXT NOT NULL UNIQUE,
    cedula INTEGER UNIQUE,
    active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS construction_sites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    name TEXT,
    active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS weeks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    year INTEGER NOT NULL,
    week_number INTEGER NOT NULL,
    UNIQUE(year, week_number)
);

CREATE TABLE IF NOT EXISTS attendance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    worker_id INTEGER NOT NULL,
    week_id INTEGER NOT NULL,
    day INTEGER NOT NULL,        -- 0=lunes .. 5=sabado
    half INTEGER NOT NULL,       -- 1 or 2
    code INTEGER NOT NULL,
    sort_order INTEGER NOT NULL,

    FOREIGN KEY(worker_id) REFERENCES workers(id),
    FOREIGN KEY(week_id) REFERENCES weeks(id),
    UNIQUE(worker_id, week_id, day, half)
);

CREATE TABLE IF NOT EXISTS payroll_reference (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    worker_id INTEGER NOT NULL,
    week_id INTEGER NOT NULL,
    salario INTEGER,
    bonus INTEGER,
    total INTEGER,
    comment TEXT,

    FOREIGN KEY(worker_id) REFERENCES workers(id),
    UNIQUE(worker_id, week_id)
);
