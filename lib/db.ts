import { Pool } from 'pg';

const pool = new Pool({
  host: process.env.DB_HOST,
  port: Number(process.env.DB_PORT),
  user: process.env.DB_USER,
  password: process.env.DB_PASSWORD,
  database: process.env.DB_NAME,
  ssl: { rejectUnauthorized: false }
});

export default {
  execute: async (query: string, params: any[]) => {
    let i = 1;
    const pgQuery = query.replace(/\?/g, () => `$${i++}`);
    const result = await pool.query(pgQuery, params);
    return [result.rows]; 
  }
};
