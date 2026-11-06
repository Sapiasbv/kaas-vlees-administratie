exec(open('/tmp/claude-0/d/link.py').read())
from openpyxl import Workbook
from openpyxl.styles import Font,PatternFill,Alignment
from openpyxl.utils import get_column_letter
NONMEAT=set(range(2400,2414))|set(range(2501,2506))|{5001}
m=ret[~ret.PLU.isin(NONMEAT)].copy().sort_values('PLU').reset_index(drop=True)
def bname(b): return bi.loc[b,'Inv_Desc']
def status(r):
    if r.how in('exact','nr'): return 'Gekoppeld'
    if r.how in('tekst','tekst~'): return 'Gekoppeld (op tekst)'
    return 'NIET gekoppeld'
m['status']=m.apply(status,axis=1)
m['bulk']=m.bulks.map(lambda x:x[0] if x else '')
# reasons for not linked
REASON={}
def R(plus,t):
    for p in plus: REASON[p]=t
R([3606,3607],'Bulk 2024700092798 heeft part nr 21405 (typfout), retail 210405')
R([3600],'Retail part nr ", Flanksteak p/kg" heeft geen nummer; bulk heeft 210403')
R([3647],'Retail part nr ", MAG MET varkens dv" mist nummer; bulk heeft 3')
R([3643],'Retail en bulk part nr schrijfwijze verschilt (snippers/snipper)')
R([3641,3651,3652],'Retail part nr "Rundersnippers 80/20 Kooten" mist nummer; bulk heeft 210190')
R([3020],'Retail 2114, bulk en weegschaal 3020: welk nummer klopt?')
R([3025],'Geen bulk-item (One time, part nr 1024000)')
R([3050],'RE part nr leeg; weegschaal zegt 2098 (Buik)')
R([5814,5802,4610,4300,4400,7900],'Retail part nr 43xxxxx; bulk heeft geen part nr')
R([3691],'Retail part nr 203691; bulk heeft geen part nr')
R([3002],'Retail part nr 40013501; bulk heeft geen part nr')
m['reden']=m.PLU.map(REASON)
m.loc[(m.status=='NIET gekoppeld')&m.reden.isna()&(m.repv==''),'reden']='Retail part nr leeg en bulk part nr leeg: geen nummer om op te koppelen'
m.loc[m.reden.isna()&(m.status=='NIET gekoppeld'),'reden']='Zie actielijst'
# note on text matches
m.loc[m.PLU.isin([3070,3699,3791]),'reden']='Gekoppeld op tekst (geen nummer in part nr)'
m.loc[m.PLU==3643,'status']='NIET gekoppeld'
print(m.status.value_counts())
print(m[m.status=='NIET gekoppeld'].reden.value_counts())
m.to_pickle('m.pkl')
# bulk -> PLU
bp=[]
for r in bulk.sort_values('Inv_Desc').itertuples():
    pl=m[m.bulk==r.Inv_Sku]
    bp.append(dict(sku=r.Inv_Sku,naam=r.Inv_Desc,vendor=r.Inv_VendorID,pv=r.pv,n=len(pl),plus=', '.join(f"{p}" for p in pl.PLU),art='; '.join(pl.Artikel.str.replace(r',?\s*p/(kg|st)\.?','',regex=True).str.strip())))
bp=pd.DataFrame(bp)
print((bp.n==0).sum(),len(bp))
bp.to_pickle('bp.pkl')
