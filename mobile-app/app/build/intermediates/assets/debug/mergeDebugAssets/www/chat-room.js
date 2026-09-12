let currentChat,peer,callId,roomId,callType='video',callSocket,pc,localStream,remoteStream,reconnectTimer=0,iceRestarted=false;
document.addEventListener('DOMContentLoaded',async()=>{await kcReady;if(!KC.currentUserId)return;mountIcons();const chats=await loadChatList();currentChat=chats.find(c=>c.id===qs('id'))||chats[0];if(!currentChat){toast('কোনো কথোপকথন নেই');return}peer=(currentChat.members||[]).find(x=>x.id!==KC.currentUserId)||kcUser(currentChat.userId);document.getElementById('peerAvatar').src=peer?.avatar||'';document.getElementById('peerNameLink').href='profile.html?id='+(peer?.id||'');document.getElementById('peerNameLink').textContent=peer?.name||'চ্যাট';await loadMessages();document.getElementById('peerCallBtn').onclick=()=>placeCall('video');document.getElementById('peerAudioBtn').onclick=()=>placeCall('audio');document.getElementById('sendBtn').onclick=sendMsg;document.getElementById('msgInput').onkeydown=e=>{if(e.key==='Enter')sendMsg();else sendTyping()};document.getElementById('attachBtn')?.addEventListener('click',()=>document.getElementById('fileInput').click());document.getElementById('fileInput')?.addEventListener('change',sendAttachment);connectRealtime();checkIncoming();if(qs('call'))placeCall('video');setInterval(loadMessages,15000);setInterval(checkIncoming,5000)});
async function loadChatList(){try{return await KC_API.get('/api/v1/conversations')}catch{return KC.chats||[]}}
async function loadMessages(){try{const ms=await KC_API.get('/api/v1/conversations/'+currentChat.id+'/messages?limit=100');KC.messages[currentChat.id]=ms.map(m=>({id:m.id,from:m.sender_id===KC.currentUserId?'me':'them',text:m.text||'',attachment:m.attachment_url||'',time:formatTime(m.created_at),read:!!m.read_at,delivered:!!m.delivered_at}));renderMessages();await KC_API.post('/api/v1/conversations/'+currentChat.id+'/read',{});}catch(e){toast(e.message)}}
function formatTime(v){try{return new Date(v).toLocaleTimeString('bn-BD',{hour:'2-digit',minute:'2-digit'})}catch{return ''}}
function renderMessages(){const body=document.getElementById('msgBody'),msgs=KC.messages[currentChat.id]||[];body.innerHTML='<div class="day-sep">আজ</div>'+msgs.map(m=>`<div class="msg-row ${m.from}">${m.from==='them'?`<img class="avatar avatar-36" src="${peer.avatar||''}">`:''}<div><div class="msg-bubble">${m.attachment?`<a href="${escapeHtml(m.attachment)}" target="_blank" rel="noopener"><img src="${escapeHtml(m.attachment)}" style="max-width:220px;max-height:220px;border-radius:10px;display:block;margin-bottom:5px" alt="সংযুক্ত ছবি"></a>`:''}${m.text?escapeHtml(m.text):''}</div><div class="msg-time">${escapeHtml(m.time||'')} ${m.from==='me'?(m.read?'✓✓':m.delivered?'✓':'') :''}</div></div></div>`).join('');body.scrollTop=body.scrollHeight}
async function sendMsg(){const input=document.getElementById('msgInput'),text=input.value.trim();if(!text)return;try{if(chatSocket?.readyState===1)chatSocket.send(JSON.stringify({text}));else await KC_API.post('/api/v1/conversations/'+currentChat.id+'/messages',{text});input.value='';await loadMessages()}catch(e){toast(e.message)}}
async function sendAttachment(e){const f=e.target.files?.[0];e.target.value='';if(!f)return;if(!/^image\/(jpeg|png|webp)$/.test(f.type)){toast('শুধু JPG/PNG/WEBP ছবি পাঠানো যাবে');return}try{const fd=new FormData();fd.append('file',f);const up=await KC_API.request('/api/v1/media/upload',{method:'POST',body:fd});await KC_API.post('/api/v1/conversations/'+currentChat.id+'/messages',{attachment_url:up.url});await loadMessages()}catch(err){toast(err.message)}}
let chatSocket;let typingTimer;function sendTyping(){if(chatSocket?.readyState===1){chatSocket.send(JSON.stringify({type:'typing',payload:{active:true}}));clearTimeout(typingTimer);typingTimer=setTimeout(()=>chatSocket?.send(JSON.stringify({type:'typing',payload:{active:false}})),1200)}}
function connectRealtime(){try{const token=localStorage.getItem('kc_access_token');if(!token)return;const apiBase=window.KC_API_BASE||localStorage.getItem('KC_API_BASE')||'http://127.0.0.1:8000';const host=new URL(apiBase).host;const proto=location.protocol==='https:'?'wss':'ws';chatSocket=new WebSocket(`${proto}://${host}/ws/conversations/${currentChat.id}?token=${encodeURIComponent(token)}`);chatSocket.onmessage=e=>{const m=JSON.parse(e.data);if(m.type==='typing'){document.getElementById('peerStatus').textContent=m.payload?.active?'লিখছেন…':'অনলাইন';return}if(m.sender_id!==KC.currentUserId){KC.messages[currentChat.id]=KC.messages[currentChat.id]||[];KC.messages[currentChat.id].push({id:m.id,from:'them',text:m.text||'',attachment:m.attachment_url||'',time:formatTime(m.created_at),delivered:true});renderMessages();KC_API.post('/api/v1/conversations/'+currentChat.id+'/read',{}).catch(()=>{})}};chatSocket.onclose=()=>{clearTimeout(reconnectTimer);reconnectTimer=setTimeout(connectRealtime,3000)}}catch(e){}}
async function placeCall(type){try{const r=await KC_API.post('/api/v1/calls',{peer_user_id:peer.id,call_type:type});callId=r.id;roomId=r.room_id;callType=type;openCallUI(false);await startMedia();connectCallSocket(true);setCallText('কল যাচ্ছে…')}catch(e){toast(e.message)}}
async function checkIncoming(){try{const rows=await KC_API.get('/api/v1/calls/incoming');const c=rows.find(x=>x.caller_id===peer?.id);if(c&&!callId){callId=c.id;roomId=c.room_id;callType=c.call_type;openCallUI(true);setCallText('ইনকামিং কল')}}catch(e){}}
function openCallUI(incoming){document.getElementById('callPanel').style.display='block';document.getElementById('acceptCall').style.display=incoming?'inline-flex':'none';document.getElementById('rejectCall').style.display=incoming?'inline-flex':'none';document.getElementById('endCall').style.display=incoming?'none':'inline-flex';document.getElementById('acceptCall').onclick=acceptCall;document.getElementById('rejectCall').onclick=()=>changeCall('rejected');document.getElementById('endCall').onclick=()=>changeCall('ended')}
async function acceptCall(){await changeCall('connected');await startMedia();connectCallSocket(false);setCallText('সংযুক্ত')}
async function changeCall(status){if(!callId)return;try{await KC_API.patch('/api/v1/calls/'+callId,{status})}catch{}if(['rejected','ended','cancelled','missed'].includes(status))cleanupCall()}
async function startMedia(){try{localStream=await navigator.mediaDevices.getUserMedia({audio:true,video:callType==='video'});document.getElementById('localVideo').srcObject=localStream;document.getElementById('localVideo').style.display='block'}catch(e){toast('ক্যামেরা/মাইক্রোফোন অনুমতি প্রয়োজন');throw e}}
async function getIceServers(){try{const r=await KC_API.get('/api/v1/calls/config');return r.ice_servers||[]}catch{return []}}
async function connectCallSocket(isCaller){
  const token=localStorage.getItem('kc_access_token');
  const proto=location.protocol==='https:'?'wss':'ws';
  const base=window.KC_API_BASE||localStorage.getItem('KC_API_BASE')||'http://127.0.0.1:8000';
  const host=new URL(base).host;
  callSocket=new WebSocket(`${proto}://${host}/ws/calls/${encodeURIComponent(roomId)}?token=${encodeURIComponent(token)}`);
  pc=new RTCPeerConnection({iceServers:await getIceServers()});
  remoteStream=new MediaStream();
  document.getElementById('remoteVideo').srcObject=remoteStream;
  pc.ontrack=e=>e.streams[0]?.getTracks().forEach(t=>remoteStream.addTrack(t));
  pc.onicecandidate=e=>{if(e.candidate)sendSignal({kind:'ice',candidate:e.candidate})};
  callSocket.onopen=async()=>{
    for(const t of localStream.getTracks())pc.addTrack(t,localStream);
    if(isCaller){const offer=await pc.createOffer();await pc.setLocalDescription(offer);sendSignal({kind:'offer',sdp:pc.localDescription})}
  };
  callSocket.onmessage=async e=>{
    const m=JSON.parse(e.data),x=m.payload||{};
    if(x.kind==='offer'){
      await pc.setRemoteDescription(x.sdp);
      const answer=await pc.createAnswer();
      await pc.setLocalDescription(answer);
      sendSignal({kind:'answer',sdp:pc.localDescription});
    }else if(x.kind==='answer'){
      await pc.setRemoteDescription(x.sdp);
    }else if(x.kind==='ice'&&x.candidate){
      try{await pc.addIceCandidate(x.candidate)}catch{}
    }
  };
  pc.onconnectionstatechange=async()=>{
    if(pc.connectionState==='connected'){
      iceRestarted=false;
      setCallText('লাইভ কল চলছে');
    }else if(['failed','disconnected'].includes(pc.connectionState)){
      setCallText('সংযোগ পুনরুদ্ধার হচ্ছে…');
      if(!iceRestarted&&pc.restartIce){
        iceRestarted=true;
        try{
          pc.restartIce();
          const offer=await pc.createOffer({iceRestart:true});
          await pc.setLocalDescription(offer);
          sendSignal({kind:'offer',sdp:pc.localDescription});
        }catch{}
      }
    }
  };
}

function sendSignal(payload){if(callSocket?.readyState===1)callSocket.send(JSON.stringify({type:'signal',payload}))}
function setCallText(t){const x=document.getElementById('callStatus');if(x)x.textContent=t}
function cleanupCall(){try{callSocket?.close()}catch{}try{pc?.close()}catch{}localStream?.getTracks().forEach(t=>t.stop());document.getElementById('callPanel').style.display='none';callId=roomId=null;iceRestarted=false}
