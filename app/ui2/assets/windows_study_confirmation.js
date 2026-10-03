  const study=replace('startStudy',async event=>{
    event.preventDefault();
    const path=value('studyPath'),status=$('studyStatus');
    if(!path){
      status.hidden=false;
      status.textContent='Seleccioná un archivo desde “Fuentes encontradas” o indicá su ruta completa dentro de la biblioteca de LexIA.';
      return;
    }
    if(studyTimer)clearTimeout(studyTimer);
    busy(study,true,'Estudiando…');
    status.hidden=false;
    status.textContent='Preparando el archivo antes de consultar la API…';
    const post=payload=>request('/api/study-start',{
      method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)
    });
    const poll=async()=>{
      try{
        const d=await request('/api/study-status'),s=d.state||{};
        status.textContent=s.status||'Estudiando…';
        if(s.phase==='awaiting_confirmation'){
          const fmt=new Intl.NumberFormat('es-AR');
          const selection=s.selection;
          if(selection?.kind==='thematic'){
            status.textContent='LexIA revisó el documento y seleccionó '+
              fmt.format(selection.regions_included||0)+' pasajes temáticos ('+
              fmt.format(selection.included_characters||0)+' caracteres) de '+
              fmt.format(selection.regions_found||0)+' zonas pertinentes. El resto del libro, doctrina o legislación no se enviará.'+
              (selection.cut_by_budget?' Algunas zonas pertinentes se recortaron por el límite del paquete.':'')+
              ' La API todavía no fue consultada.';
          }else{
            const detail=s.truncation||{};
            const included=Number(detail.included||0),available=Number(detail.available||0);
            const omitted=Math.max(0,available-included);
            status.textContent='El archivo excede el límite del estudio: '+fmt.format(available)+
              ' caracteres disponibles; LexIA enviaría '+fmt.format(included)+' y dejaría afuera '+
              fmt.format(omitted)+'. La API todavía no fue consultada. El análisis parcial puede omitir partes decisivas.';
          }
          const actions=document.createElement('div');
          actions.className='context-actions';
          const confirm=document.createElement('button');
          confirm.type='button';confirm.className='primary';confirm.textContent=selection?'Enviar pasajes seleccionados':'Enviar análisis parcial';
          const cancel=document.createElement('button');
          cancel.type='button';cancel.className='secondary';cancel.textContent='Cancelar sin costo';
          actions.append(confirm,cancel);
          status.append(actions);
          busy(study,false,'Estudiar');
          confirm.addEventListener('click',async()=>{
            confirm.disabled=true;cancel.disabled=true;actions.remove();
            busy(study,true,'Estudiando…');
            status.textContent='Enviando el estudio confirmado…';
            try{await post({confirm_job_id:s.job_id});poll();}
            catch(error){status.textContent=error.message||String(error);busy(study,false,'Estudiar');}
          });
          cancel.addEventListener('click',async()=>{
            confirm.disabled=true;cancel.disabled=true;actions.remove();
            try{await post({cancel_job_id:s.job_id});status.textContent='Estudio cancelado. No se consultó la API.';}
            catch(error){status.textContent=error.message||String(error);}
            busy(study,false,'Estudiar');
          });
          return;
        }
        if(s.phase==='completed'){
          const r=await request('/api/study-result');
          lastContent=String(r.result?.content||'');
          text('investigationOutput',lastContent);
          text('outputSourceCount',r.result?.source_count||1);
          text('outputDocumentCount',r.result?.document_count||1);
          text('outputState','Listo');
          busy(study,false,'Estudiar');
          return;
        }
        if(s.phase==='error'){
          status.textContent='No se pudo estudiar el archivo.\n\n'+(s.error||s.status||'');
          busy(study,false,'Estudiar');
          return;
        }
        studyTimer=setTimeout(poll,700);
      }catch(error){status.textContent=error.message||String(error);busy(study,false,'Estudiar');}
    };
    try{
      await post({
        path,objective:$('studyObjective')?.value||'Análisis de jurisprudencia',
        instruction:value('studyInstruction'),document_type:$('studyType')?.value||'Detección automática'
      });
      poll();
    }catch(error){status.textContent=error.message||String(error);busy(study,false,'Estudiar');}
  });