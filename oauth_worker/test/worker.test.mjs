import test from 'node:test';
import assert from 'node:assert/strict';
import worker,{GachaAuth,hash,allowedAPI} from '../src/worker.js';
const origin='https://osu-gacha-auth.therealdimedrol.workers.dev';
function fixture(){
  const data=new Map();
  const storage={async get(k){return structuredClone(data.get(k));},async put(k,v){data.set(k,structuredClone(v));},async deleteAll(){data.clear();},async setAlarm(){}};
  const ctx={storage,blockConcurrencyWhile:fn=>fn()};
  return {auth:new GachaAuth(ctx,{PUBLIC_ORIGIN:origin,OSU_CLIENT_ID:'test-id',OSU_CLIENT_SECRET:'server-only-fixture'}),storage};
}
test('endpoint allowlist is restricted to own scores and standard beatmaps',()=>{
  assert(allowedAPI('users/6/scores/recent','GET','6'));
  assert(!allowedAPI('users/7/scores/recent','GET','6'));
  assert(!allowedAPI('https://attacker.invalid','GET','6'));
  assert(!allowedAPI('beatmaps/1/../../me','GET','6'));
  assert(!allowedAPI('users/6/osu','POST','6'));
});
test('browser proof, one-use callback, private tokens, refresh and logout',async()=>{
  const {auth,storage}=fixture();const id='1'.repeat(64),verifier='2'.repeat(64);
  const call=(path,method='GET',body,headers={})=>auth.fetch(new Request(origin+path,{method,headers,...(body?{body:JSON.stringify(body)}:{})}));
  let response=await call('/internal/start','POST',{id,challenge:await hash(verifier)});assert.equal(response.status,200);
  response=await call('/login');assert.equal(response.status,302);
  const state=new URL(response.headers.get('Location')).searchParams.get('state');
  const cookie=response.headers.get('Set-Cookie').split(';')[0];
  assert.equal((await call('/oauth/callback?code=test&state='+state)).status,400);
  let refreshes=0;const saved=globalThis.fetch;
  globalThis.fetch=async(url,options)=>{
    if(url.endsWith('/oauth/token')){
      const data=Object.fromEntries(new URLSearchParams(options.body));assert.equal(data.client_secret,'server-only-fixture');
      if(data.grant_type==='refresh_token')refreshes++;
      return Response.json({access_token:'upstream-access-fixture',refresh_token:'upstream-refresh-fixture',expires_in:3600});
    }
    assert.equal(options.headers.Authorization,'Bearer upstream-access-fixture');
    return Response.json(url.includes('/scores/')?[]:{id:6,username:'Fixture',statistics:{pp:1500}});
  };
  try{
    response=await call('/oauth/callback?code=test&state='+state,'GET',null,{Cookie:cookie});assert.equal(response.status,200);
    assert.equal((await call('/oauth/callback?code=test&state='+state,'GET',null,{Cookie:cookie})).status,400);
    assert.equal((await call('/desktop/poll','POST',{id,verifier:'3'.repeat(64)})).status,401);
    response=await call('/desktop/poll','POST',{id,verifier});const result=await response.json();assert.equal(result.user.id,6);
    assert.equal(result.session,id+'.'+verifier);assert(!JSON.stringify(result).includes('upstream'));
    const headers={Authorization:'Bearer '+result.session};
    assert.equal((await call('/api/v2/users/7/osu','GET',null,headers)).status,403);
    const login=await storage.get('login');login.tokens.expires=0;await storage.put('login',login);
    response=await call('/api/v2/users/6/osu','GET',null,headers);assert.equal(response.status,200);assert.equal(refreshes,1);
    assert(!JSON.stringify(await response.json()).includes('upstream'));
    assert.equal((await call('/logout','POST',{},headers)).status,200);
    assert.equal((await call('/session','GET',null,headers)).status,401);
  }finally{globalThis.fetch=saved;}
});
test('expired login cannot authorize',async()=>{
  const {auth,storage}=fixture();await storage.put('login',{id:'1'.repeat(64),expires:0});
  assert.equal((await auth.fetch(new Request(origin+'/login'))).status,410);
});
test('SkillPush CORS, web login and public map catalogue stay available',async()=>{
  const objects=new Map(),env={PUBLIC_ORIGIN:origin,OSU_CLIENT_ID:'fixture'};
  env.GACHA_AUTH={idFromName:id=>id,get(id){if(!objects.has(id)){const {auth}=fixture();auth.env=env;objects.set(id,auth);}return objects.get(id);}};
  const webOrigin='https://skillpush.therealdimedrol.workers.dev';
  let response=await worker.fetch(new Request(origin+'/desktop/start',{method:'OPTIONS',headers:{Origin:webOrigin}}),env);
  assert.equal(response.status,204);assert.equal(response.headers.get('Access-Control-Allow-Origin'),webOrigin);
  response=await worker.fetch(new Request(origin+'/desktop/start',{method:'POST',headers:{Origin:'https://untrusted.invalid'},body:JSON.stringify({challenge:'a'.repeat(64)})}),env);
  assert.equal(response.status,403);
  response=await worker.fetch(new Request(origin+'/desktop/start',{method:'POST',headers:{Origin:webOrigin},body:JSON.stringify({challenge:'a'.repeat(64)})}),env);
  const start=await response.json();assert.equal(response.status,200);
  assert.equal((await objects.get(start.id).ctx.storage.get('login')).webOrigin,webOrigin);
  response=await worker.fetch(new Request(origin+'/app/maps',{headers:{Origin:webOrigin}}),env);
  assert.equal(response.status,200);assert.deepEqual((await response.json()).maps,[]);
  assert.equal(response.headers.get('Access-Control-Allow-Origin'),webOrigin);
  assert(allowedAPI('beatmapsets/1/download','GET','6'));
});
