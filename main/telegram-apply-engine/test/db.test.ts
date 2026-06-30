import { describe, it, expect, beforeEach } from 'vitest';
import { initializeDatabase } from '../src/db/db';
import type Database from 'better-sqlite3';

describe('Database Schema and CRUD', () => {
  let db: Database.Database;

  beforeEach(() => {
    // Run an in-memory database for fresh tests
    db = initializeDatabase(':memory:');
  });

  it('should insert and retrieve a user', () => {
    const insert = db.prepare('INSERT INTO users (id, telegram_user_id) VALUES (?, ?)');
    insert.run('user_123', 'tg_456');

    const select = db.prepare('SELECT * FROM users WHERE id = ?');
    const user = select.get('user_123') as any;

    expect(user).toBeDefined();
    expect(user.telegram_user_id).toBe('tg_456');
    expect(user.created_at).toBeDefined();
  });

  it('should enforce unique telegram_user_id', () => {
    const insert = db.prepare('INSERT INTO users (id, telegram_user_id) VALUES (?, ?)');
    insert.run('user_1', 'tg_shared');

    expect(() => {
      insert.run('user_2', 'tg_shared');
    }).toThrow(/UNIQUE constraint failed/);
  });

  it('should handle user profile linking', () => {
    const insertUser = db.prepare('INSERT INTO users (id, telegram_user_id) VALUES (?, ?)');
    insertUser.run('u1', 't1');

    const profileJson = JSON.stringify({ first_name: 'Bhawani', last_name: 'Singh' });
    const insertProfile = db.prepare('INSERT INTO user_profiles (user_id, profile_json) VALUES (?, ?)');
    insertProfile.run('u1', profileJson);

    const select = db.prepare('SELECT * FROM user_profiles WHERE user_id = ?');
    const profile = select.get('u1') as any;

    expect(profile.profile_json).toBe(profileJson);
  });

  it('should enforce foreign key constraint for user_profiles', () => {
    const profileJson = JSON.stringify({ name: 'Invalid' });
    const insertProfile = db.prepare('INSERT INTO user_profiles (user_id, profile_json) VALUES (?, ?)');
    
    expect(() => {
      insertProfile.run('does_not_exist', profileJson);
    }).toThrow(/FOREIGN KEY constraint failed/);
  });
});
