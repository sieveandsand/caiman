## What matter in a board config file?
- Chip name --> from there we can infer the use cases and roles
- peripheral
- external connections
- board level docuemntation

should not lock in to a single industry format. 
should be the greatest common denominator... debatable

board config is only to describe the board at a architecture level. 

who would fill out this? 


-----------
openscope provides a good insight where they are parts first. a part is the primitive component in the project, and there are document(s) that accompanies that part. 

so the question for us: is caiman a parts manager or a document manager? I think caiman should be a document manager since this is the painpoint I discovered during work.